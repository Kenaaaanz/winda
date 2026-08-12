import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message
from ..notifications.models import Notification

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'text')
        content = data.get('content', '')
        
        if message_type == 'typing':
            await self.send_typing_status()
        else:
            # Save message to database
            message = await self.save_message(content, message_type)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(message.id),
                        'sender': {
                            'id': str(message.sender.id),
                            'full_name': message.sender.get_full_name(),
                            'profile_picture': str(message.sender.profile_picture.url) if message.sender.profile_picture else None,
                        },
                        'content': message.content,
                        'message_type': message.message_type,
                        'file_url': str(message.file.url) if message.file else None,
                        'created_at': message.created_at.isoformat(),
                    }
                }
            )
            
            # Create notifications for other participants
            await self.create_notifications(message)
    
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message']
        }))
    
    async def send_typing_status(self):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'data': {
                'user': self.scope['user'].get_full_name(),
                'is_typing': True
            }
        }))
    
    @database_sync_to_async
    def save_message(self, content, message_type):
        room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            room=room,
            sender=self.scope['user'],
            message_type=message_type.upper(),
            content=content
        )
        return message
    
    @database_sync_to_async
    def create_notifications(self, message):
        room = message.room
        for participant in room.participants.exclude(id=message.sender.id):
            Notification.objects.create(
                user=participant,
                notification_type='MESSAGE',
                title=f'New message from {message.sender.get_full_name()}',
                message=message.content[:100],
                related_object_type='chat_message',
                related_object_id=str(message.id),
                data={
                    'chat_room_id': str(room.id),
                    'sender_id': str(message.sender.id),
                    'message_preview': message.content[:50]
                }
            )

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.notification_group_name = f'user_{self.user.id}_notifications'
        
        # Join user notification group
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send unread count
        await self.send_unread_count()
    
    async def disconnect(self, close_code):
        # Leave notification group
        await self.channel_layer.group_discard(
            self.notification_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data.get('type') == 'mark_read':
            await self.mark_notification_read(data.get('notification_id'))
    
    async def send_notification(self, event):
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['notification']
        }))
        
        # Send updated unread count
        await self.send_unread_count()
    
    @database_sync_to_async
    def send_unread_count(self):
        from ..notifications.models import Notification
        count = Notification.objects.filter(
            user=self.user,
            is_read=False
        ).count()
        
        self.send(text_data=json.dumps({
            'type': 'unread_count',
            'data': {'count': count}
        }))
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from ..notifications.models import Notification
        try:
            notification = Notification.objects.get(id=notification_id, user=self.user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
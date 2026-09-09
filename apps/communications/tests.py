from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import ChatRoom, Message

User = get_user_model()


class ChatStartTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.sender = User.objects.create_user(
			username='tenant@example.com',
			email='tenant@example.com',
			password='testpassword123',
			user_type='TENANT',
		)
		self.recipient = User.objects.create_user(
			username='owner@example.com',
			email='owner@example.com',
			password='testpassword123',
			user_type='HOUSE_OWNER',
		)
		self.client.force_login(self.sender)

	def test_start_chat_page_renders_without_target(self):
		response = self.client.get(reverse('communications:start_chat'), secure=True)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Start a Chat')

	def test_post_from_start_conversation_redirects_to_chat_detail(self):
		response = self.client.post(reverse('communications:start_chat'), {
			'user_id': str(self.recipient.id),
			'initial_message': 'I am interested in this property.',
		}, secure=True)

		room = ChatRoom.objects.get(participants=self.sender, room_type='PRIVATE')
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('communications:chat_detail', kwargs={'room_id': room.id}))
		self.assertTrue(Message.objects.filter(room=room, content='I am interested in this property.').exists())

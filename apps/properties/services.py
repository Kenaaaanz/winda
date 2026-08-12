from django.db.models import Q
from .models import Property

class PropertyService:
    @staticmethod
    def get_amenities_list():
        return [
            'Swimming Pool', 'Gym', 'Parking', 'Security', 'Elevator',
            'Balcony', 'Garden', 'Playground', 'Clubhouse', 'Laundry',
            'Air Conditioning', 'Heating', 'Internet', 'Cable TV',
            'Water Heater', 'Solar Panels', 'Backup Generator'
        ]
    
    @staticmethod
    def get_features_list():
        return [
            'Tiled Flooring', 'Wooden Flooring', 'Modern Kitchen',
            'Walk-in Closet', 'Jacuzzi', 'Fireplace', 'Smart Home',
            'Energy Efficient', 'Pet Friendly', 'Wheelchair Accessible'
        ]
    
    @staticmethod
    def get_similar_properties(property, limit=6):
        return Property.objects.filter(
            Q(city=property.city) | 
            Q(property_type=property.property_type),
            verification_status='VERIFIED',
            availability_status='AVAILABLE'
        ).exclude(pk=property.pk)[:limit]
    
    @staticmethod
    def calculate_occupancy_rate(owner):
        properties = Property.objects.filter(owner=owner)
        total = properties.count()
        if total == 0:
            return 0
        occupied = properties.filter(availability_status='RENTED').count()
        return (occupied / total) * 100


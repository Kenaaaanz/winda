# apps/analytics/migrations/XXXX_fix_user_activity_uuid.py
from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('analytics', '0002_analyticsdashboard_analyticsmetric_analyticsreport_and_more'),  
    ]

    operations = [
        # Remove the existing table and recreate it with UUID
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS analytics_user_activities CASCADE;
                CREATE TABLE analytics_user_activities (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id),
                    activity_type VARCHAR(20) NOT NULL,
                    description TEXT NOT NULL,
                    related_object_type VARCHAR(50),
                    related_object_id VARCHAR(50),
                    data JSONB DEFAULT '{}',
                    ip_address INET,
                    user_agent TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
                CREATE INDEX analytics_user_activities_user_id_created_at_idx 
                    ON analytics_user_activities(user_id, created_at);
                CREATE INDEX analytics_user_activities_activity_type_created_at_idx 
                    ON analytics_user_activities(activity_type, created_at);
            """,
            reverse_sql="DROP TABLE analytics_user_activities;"
        ),
    ]
"""Request and response schema definitions for API validation.

This module contains Marshmallow schemas for validating API requests
and responses throughout the LPS2 application.
"""
from marshmallow import Schema, fields, validate, validates, ValidationError

# Auth schemas
class LoginSchema(Schema):
    """Schema for login requests."""
    username = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    password = fields.Str(required=True, validate=validate.Length(min=1))
    
    @validates('username')
    def validate_username(self, value):
        if not value.strip():
            raise ValidationError("Username cannot be empty or whitespace")

# Chat schemas
class ChatMessageSchema(Schema):
    """Schema for chat message requests."""
    message = fields.Str(required=True, validate=validate.Length(min=1, max=10000))
    conversation_id = fields.Str(allow_none=True)
    context_id = fields.List(fields.Str(), allow_none=True)
    csrf_token = fields.Str(allow_none=True)
    
    @validates('message')
    def validate_message(self, value):
        if not value.strip():
            raise ValidationError("Message cannot be empty or whitespace")

class SearchMemorySchema(Schema):
    """Schema for memory search requests."""
    query = fields.Str(required=True, validate=validate.Length(min=1, max=1000))
    top_k = fields.Int(missing=5, validate=validate.Range(min=1, max=50))
    
    @validates('query')
    def validate_query(self, value):
        if not value.strip():
            raise ValidationError("Query cannot be empty or whitespace")

class AddMemorySchema(Schema):
    """Schema for adding memories."""
    text = fields.Str(required=True, validate=validate.Length(min=1, max=10000))
    metadata = fields.Dict(missing=dict)
    
    @validates('text')
    def validate_text(self, value):
        if not value.strip():
            raise ValidationError("Text cannot be empty or whitespace")

# Endpoint profile schemas
class EndpointTestSchema(Schema):
    """Schema for endpoint testing requests."""
    endpoint = fields.Str(required=True)
    csrf_token = fields.Str(allow_none=True)
    
    @validates('endpoint')
    def validate_endpoint(self, value):
        if not value.strip():
            raise ValidationError("Endpoint cannot be empty")
        if not value.strip().startswith("http://") and not value.strip().startswith("https://"):
            raise ValidationError("Endpoint must start with http:// or https://")

class ProfileUpsertSchema(Schema):
    """Schema for profile creation/update requests."""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    endpoint = fields.Str(required=True)
    persist = fields.Bool(missing=False)
    csrf_token = fields.Str(allow_none=True)
    
    @validates('name')
    def validate_name(self, value):
        if not value.strip():
            raise ValidationError("Profile name cannot be empty")
    
    @validates('endpoint')
    def validate_endpoint(self, value):
        if not value.strip():
            raise ValidationError("Endpoint cannot be empty")
        if not value.strip().startswith("http://") and not value.strip().startswith("https://"):
            raise ValidationError("Endpoint must start with http:// or https://")

class ProfileActivateSchema(Schema):
    """Schema for profile activation requests."""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    persist = fields.Bool(missing=False)
    csrf_token = fields.Str(allow_none=True)

class ProfileDeleteSchema(Schema):
    """Schema for profile deletion requests."""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    persist = fields.Bool(missing=False)
    csrf_token = fields.Str(allow_none=True)
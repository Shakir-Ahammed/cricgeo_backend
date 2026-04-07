# OTP Authentication System

## Overview

A production-ready, mobile-first OTP (One-Time Password) authentication system for FastAPI. Users authenticate using email and 6-digit OTP codes with automatic user creation and profile completion.

---

## Features

- ✅ Email-based OTP authentication (no passwords)
- ✅ 6-digit numeric OTP codes
- ✅ 5-minute OTP expiration
- ✅ Rate limiting (3 requests/minute)
- ✅ Max 5 verification attempts
- ✅ Automatic user creation
- ✅ Step-by-step profile completion
- ✅ JWT token authentication
- ✅ Secure OTP hashing (SHA256)

---

## API Endpoints

### 1. Request OTP
```http
POST /auth/request-otp
Content-Type: application/json

{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "OTP sent to your email. Valid for 5 minutes.",
  "data": {
    "email": "user@example.com"
  }
}
```

### 2. Verify OTP
```http
POST /auth/verify-otp
Content-Type: application/json

{
  "email": "user@example.com",
  "otp": "123456"
}
```

**Response (New User):**
```json
{
  "success": true,
  "message": "OTP verified successfully",
  "data": {
    "access_token": "eyJhbGc...",
    "is_new_user": true,
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**Response (Existing User):**
```json
{
  "success": true,
  "message": "OTP verified successfully",
  "data": {
    "access_token": "eyJhbGc...",
    "is_new_user": false,
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### 3. Complete Profile
```http
POST /auth/complete-profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "John Doe",
  "gender": "male",
  "phone": "+1234567890",
  "profile_image": "https://example.com/image.jpg"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Profile completed successfully. Welcome!",
  "data": {
    "user": {
      "id": 1,
      "name": "John Doe",
      "email": "user@example.com",
      "phone": "+1234567890",
      "gender": "male",
      "profile_image": "https://example.com/image.jpg",
      "profile_completed": true,
      ...
    }
  }
}
```

---

## User Flow

### New User
```
1. Enter email → Request OTP
2. Receive OTP via email (6 digits, valid 5 minutes)
3. Enter OTP → Verify
4. Response: is_new_user = true
5. Complete profile (name, gender, phone, image)
6. Access app
```

### Existing User
```
1. Enter email → Request OTP
2. Receive OTP via email
3. Enter OTP → Verify
4. Response: is_new_user = false
5. Access app directly
```

---

## Mobile Integration

### React Native Example

```javascript
import AsyncStorage from '@react-native-async-storage/async-storage';

// 1. Request OTP
const requestOTP = async (email) => {
  const response = await fetch('https://api.example.com/auth/request-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
  return response.json();
};

// 2. Verify OTP
const verifyOTP = async (email, otp) => {
  const response = await fetch('https://api.example.com/auth/verify-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp })
  });
  
  const result = await response.json();
  
  if (result.success) {
    // Store token
    await AsyncStorage.setItem('token', result.data.access_token);
    
    // Check if new user
    if (result.data.is_new_user) {
      navigation.navigate('CompleteProfile');
    } else {
      navigation.navigate('Home');
    }
  }
  
  return result;
};

// 3. Complete Profile
const completeProfile = async (profileData) => {
  const token = await AsyncStorage.getItem('token');
  
  const response = await fetch('https://api.example.com/auth/complete-profile', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(profileData)
  });
  
  return response.json();
};
```

### Flutter Example

```dart
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

class AuthService {
  static const String baseUrl = 'https://api.example.com';
  
  // Request OTP
  static Future<Map<String, dynamic>> requestOTP(String email) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/request-otp'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email}),
    );
    
    return jsonDecode(response.body);
  }
  
  // Verify OTP
  static Future<Map<String, dynamic>> verifyOTP(String email, String otp) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/verify-otp'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'otp': otp}),
    );
    
    final data = jsonDecode(response.body);
    
    if (data['success']) {
      // Store token
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('token', data['data']['access_token']);
    }
    
    return data;
  }
  
  // Complete Profile
  static Future<Map<String, dynamic>> completeProfile({
    required String name,
    required String gender,
    required String phone,
    String? profileImage,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    
    final response = await http.post(
      Uri.parse('$baseUrl/auth/complete-profile'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'name': name,
        'gender': gender,
        'phone': phone,
        if (profileImage != null) 'profile_image': profileImage,
      }),
    );
    
    return jsonDecode(response.body);
  }
}
```

---

## Security

- **OTP Hashing:** SHA256 (never stored plain)
- **Expiration:** 5 minutes
- **Rate Limiting:** 3 requests per minute per email
- **Max Attempts:** 5 verification attempts per OTP
- **JWT Tokens:** 30-minute expiration (configurable)

---

## Error Handling

| Error | HTTP Code | Message |
|-------|-----------|---------|
| Rate limited | 429 | "Too many OTP requests" |
| Invalid OTP | 400 | "Invalid OTP. X attempts remaining" |
| Expired OTP | 400 | "Invalid or expired OTP" |
| Max attempts | 400 | "Maximum attempts exceeded" |
| Invalid gender | 400 | "Invalid gender. Must be male, female, or other" |
| Profile completed | 400 | "Profile already completed" |
| Unauthorized | 401 | "Missing authorization header" |

---

## Testing

### Request OTP
```bash
curl -X POST http://localhost:8000/auth/request-otp \
  -H 'Content-Type: application/json' \
  -d '{"email": "test@example.com"}'
```

### Verify OTP
```bash
curl -X POST http://localhost:8000/auth/verify-otp \
  -H 'Content-Type: application/json' \
  -d '{"email": "test@example.com", "otp": "123456"}'
```

### Complete Profile
```bash
curl -X POST http://localhost:8000/auth/complete-profile \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{
    "name": "John Doe",
    "gender": "male",
    "phone": "+1234567890"
  }'
```

---

## Database Schema

### OTP Table
```sql
CREATE TABLE otps (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(255) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### User Table (New Fields)
```sql
ALTER TABLE users ADD COLUMN profile_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN gender VARCHAR(10);
ALTER TABLE users ADD COLUMN profile_image VARCHAR(500);
ALTER TABLE users ALTER COLUMN name DROP NOT NULL;
```

---

## Configuration

Required environment variables in `.env`:

```env
# JWT
JWT_SECRET=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email (SMTP)
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM_ADDRESS=noreply@example.com
MAIL_FROM_NAME=Your App Name
```

---

## Troubleshooting

### OTP Email Not Received
1. Check spam folder
2. Verify email configuration in `.env`
3. Check server logs for email errors

### OTP Verification Fails
1. Ensure OTP entered within 5 minutes
2. Check for typos
3. Request new OTP if needed

### Rate Limiting
1. Wait 1 minute before retry
2. Maximum 3 requests per minute per email

---

## API Documentation

Full API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

**For more details, see the complete API documentation at `/docs`**

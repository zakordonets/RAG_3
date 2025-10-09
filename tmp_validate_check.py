from app.infrastructure import validate_request
print(validate_request(user_id='u1', message='Hello. Test.', channel='telegram', chat_id=274050222))

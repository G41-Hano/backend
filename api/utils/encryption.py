from cryptography.fernet import Fernet
from django.conf import settings

f = Fernet(settings.ENCRYPTION_KEY)

# ex. 
# data value is 'Hello World', 
# after decrypting, it will return:
# 'gAAAAABoAlUUVUESw4coyFFzHXJ35tEBjVXY2SjcIddKQAw2VJRWMSOiLpivmomefKMAY2T66C52s53F9Ok-aXD71EnjhdHtrA=='
def encrypt(data):
  """
  encrypts the data using the ENCRYPTION_KEY

  Parameters:
    data (str): the text you wish to encrypt

  Returns:
    byte: The encrypted value\n
    None: if data is empty or does not exist
  """
  if data:
    return f.encrypt(data.encode())
  return None

# ex. 
# data value is 'gAAAAABoAlUUVUESw4coyFFzHXJ35tEBjVXY2SjcIddKQAw2VJRWMSOiLpivmomefKMAY2T66C52s53F9Ok-aXD71EnjhdHtrA==', 
# after decrypting, it will return: 'Hello World'
def decrypt(data):
  """
  decrypts the data using the ENCRYPTION_KEY

  Parameters:
    data (byte): the encrypted data you wish to decrypt

  Returns:
    str: The encrypted value\n
    None: if data is empty or does not exist
  """
  if data:
    # print("data is of type: ",type(data))
    if isinstance(data, memoryview):
      data = data.tobytes()
       
    return f.decrypt(data).decode()
  return None
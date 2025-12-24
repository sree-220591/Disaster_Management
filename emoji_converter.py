message = input("PLease enter your emotion: \n eg(happy,sad,crying,laughing etc..)")
emotion = message.lower()
emojis_mapping = {
    "smile": "😄",
    "sad": "😢",
    "heart": "❤️",
    "laughing": "😂",
    "crying": "😭",
    "angry": "😠",
    "surprised": "😲",
    "love": "😍"
}

output=''

output += emojis_mapping.get(emotion,emotion)
print(f"So uh are {emotion} {output}!")
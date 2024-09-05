import time
import anthropic

from k4_voice_dictionary import voice_dictionary_ids, get_voice_name_by_id


client = anthropic.Anthropic(
    api_key='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',
)

def get_voice_id(key):
    return voice_dictionary_ids[key]["Voice ID"]


def pick_voice(visualPrompt):
    try:
        adminVoicePickerPrompt = (
            f"I want you to pick ONE of these many voice options based on which will best suit the following character description:"
            f"{visualPrompt}"
            f"you must reply ONLY with the KEY NUMBER and nothing else, this is a json parsing operation so please reply ONLY instantly with ONLY the VoiceNumber and nothing else, "
            f"here is the dictionary, return ONLY the KEY number that best fits: {voice_dictionary_ids}"
        )

        max_attempts = 3  # Maximum number of attempts to pick a valid voice
        attempt = 1

        while attempt <= max_attempts:
            # Generate a response from OpenAI API
            response =  client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[
            {"role": "user", "content": adminVoicePickerPrompt}
        ]
    )
            # Extract the assistant's message from the response
            chosen_KEYvoice_number = response.content[0].text

            # Print the chosen key number for debugging
            print(
                f"Attempt {attempt}: Chosen key number from AI: {chosen_KEYvoice_number}"
            )

            # Filter out any characters that are not digits
            chosen_KEYvoice_number = int(
                "".join(filter(str.isdigit, chosen_KEYvoice_number))
            )

            try:
                # Retrieve the voice ID using the chosen key
                chosenVoiceID = get_voice_id(chosen_KEYvoice_number)
                return chosenVoiceID
            except KeyError:
                # If the chosen key is not found, try again with the next closest key
                print(f"Attempt {attempt}: Voice ID not available. Trying again...")
                attempt += 1
                time.sleep(2)  # Wait for 2 seconds before making another attempt

        # If no valid voice is found after max_attempts, return an error message
        return {"message": "Error: Unable to find a suitable voice."}

    except Exception as err:
        return {"message": "Error with generating voice", "error": err}



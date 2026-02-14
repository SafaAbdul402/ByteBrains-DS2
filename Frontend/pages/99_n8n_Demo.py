import os
import time
import uuid
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
N8N_ROUTE_SECRET = os.getenv("N8N_ROUTE_SECRET", "devsecret")

st.set_page_config(page_title="ByteBrains – n8n Demo", layout="wide")
st.title("n8n Demo Sender")

if not API_BASE:
    st.error("API_BASE is not set. Add it to your environment variables.")
    st.stop()

# --- Demo-only hint (optional)
if not DEMO_MODE:
    st.warning("DEMO_MODE is off. This page is intended for demo deployments.")

# -----------------------
# Payload (exact same shape)
# -----------------------
def build_demo_payload(meeting_id: str) -> dict:
    # ✅ EXACT shape used by production:
    # {"meeting_id": str, "transcript": [..], "profiles": [..]}
    return {
        "meeting_id": "meeting-1771100600",
        "transcript": [
            {
            "start": 0.03,
            "end": 0.87,
            "speaker": "Johannes Wowra",
            "text": "Hello."
            },
            {
            "start": 0.87,
            "end": 2.3499999999999996,
            "speaker": "Johannes Wowra",
            "text": "I should hear a voice message."
            },
            {
            "start": 2.3499999999999996,
            "end": 4.11,
            "speaker": "Johannes Wowra",
            "text": "Okay, so if you hear us, we don't hear you."
            },
            {
            "start": 4.11,
            "end": 4.95,
            "speaker": "Johannes Wowra",
            "text": "You're muted."
            },
            {
            "start": 4.95,
            "end": 6.87,
            "speaker": "Johannes Wowra",
            "text": "So will you make, we'll be able to make it work."
            },
            {
            "start": 6.87,
            "end": 8.27,
            "speaker": "Johannes Wowra",
            "text": "Can you hear us by the way?"
            },
            {
            "start": 8.06,
            "end": 14.940000000000001,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Could we've created a PowerPoint? Yeah, Morgan's okay. Maybe he can share a screen and like one of us can explain it"
            },
            {
            "start": 14.24,
            "end": 16.64,
            "speaker": "Safa V Abdul Ravuf",
            "text": "explain it."
            },
            {
            "start": 15.74,
            "end": 17.1,
            "speaker": "Farshad Soleimani",
            "text": "I can also not hear us."
            },
            {
            "start": 17.1,
            "end": 19.62,
            "speaker": "Farshad Soleimani",
            "text": "So, we have this thing."
            },
            {
            "start": 19.62,
            "end": 22.62,
            "speaker": "Farshad Soleimani",
            "text": "We decided to work on the AI workflow automation."
            },
            {
            "start": 22.62,
            "end": 23.7,
            "speaker": "Farshad Soleimani",
            "text": "Okay."
            },
            {
            "start": 23.7,
            "end": 25.259999999999998,
            "speaker": "Farshad Soleimani",
            "text": "This..."
            },
            {
            "start": 25.259999999999998,
            "end": 27.78,
            "speaker": "Farshad Soleimani",
            "text": "So, this was the automation we thought."
            },
            {
            "start": 27.78,
            "end": 31.740000000000002,
            "speaker": "Farshad Soleimani",
            "text": "The steps we thought we would have."
            },
            {
            "start": 31.740000000000002,
            "end": 36.22,
            "speaker": "Farshad Soleimani",
            "text": "We could also have other steps in future."
            },
            {
            "start": 36.22,
            "end": 39.06,
            "speaker": "Farshad Soleimani",
            "text": "We have a Python code for voice recognition"
            },
            {
            "start": 39.06,
            "end": 44.42,
            "speaker": "Farshad Soleimani",
            "text": "and giving labels to each speaker."
            },
            {
            "start": 44.42,
            "end": 47.7,
            "speaker": "Farshad Soleimani",
            "text": "So, we can differentiate between different speakers."
            },
            {
            "start": 49.46,
            "end": 53.06,
            "speaker": "Farshad Soleimani",
            "text": "Then give the voice to the..."
            },
            {
            "start": 53.06,
            "end": 55.580000000000005,
            "speaker": "Farshad Soleimani",
            "text": "Sorry, are you on the left or are you on the right?"
            },
            {
            "start": 56.12,
            "end": 57.64,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Right side, AI meeting assist."
            },
            {
            "start": 57.34,
            "end": 60.620000000000005,
            "speaker": "Johannes Wowra",
            "text": "On the left side, I think. Do you see my cursor?"
            },
            {
            "start": 60.620000000000005,
            "end": 63.980000000000004,
            "speaker": "Johannes Wowra",
            "text": "Yeah, I see your cursor because you're talking about speaker but you're pointing to the left."
            },
            {
            "start": 63.980000000000004,
            "end": 64.94,
            "speaker": "Johannes Wowra",
            "text": "That's why I'm confused."
            },
            {
            "start": 65.1,
            "end": 73.46,
            "speaker": "Farshad Soleimani",
            "text": "I'm just first explaining this thing, they will give the transcripts that are generated"
            },
            {
            "start": 73.46,
            "end": 81.94,
            "speaker": "Farshad Soleimani",
            "text": "to the OpenNI API and giving a prompt to it so that it could understand and differentiate"
            },
            {
            "start": 84.03,
            "end": 88.83,
            "speaker": "Johannes Wowra",
            "text": "Sorry, sorry, you're talking about different speakers, but this is, you're talking about"
            },
            {
            "start": 88.83,
            "end": 89.83,
            "speaker": "Johannes Wowra",
            "text": "the right side."
            },
            {
            "start": 89.83,
            "end": 91.99,
            "speaker": "Johannes Wowra",
            "text": "I think the both are so obvious, yes."
            },
            {
            "start": 91.97,
            "end": 102.69,
            "speaker": "Farshad Soleimani",
            "text": "So we would make a transcript from the meeting and give it to the API prompts and open an"
            },
            {
            "start": 102.69,
            "end": 112.93,
            "speaker": "Farshad Soleimani",
            "text": "array and it would generate tasks and also it would give out all of the meetings invitation."
            },
            {
            "start": 113.33,
            "end": 122.53,
            "speaker": "Farshad Soleimani",
            "text": "For example, if we have decided to use API for Treadle 2, but if we have difficulties, we may"
            },
            {
            "start": 123.41,
            "end": 131.41,
            "speaker": "Farshad Soleimani",
            "text": "email each people, each person and from the transcripts it will make live meeting notes."
            },
            {
            "start": 131.41,
            "end": 140.53,
            "speaker": "Farshad Soleimani",
            "text": "So it will save notes and transcriptions and it will automatically assign tasks to each person."
            },
            {
            "start": 141.49,
            "end": 148.05,
            "speaker": "Farshad Soleimani",
            "text": "As the input, it will give the capabilities and roles of each person from that meeting"
            },
            {
            "start": 148.61,
            "end": 156.05,
            "speaker": "Farshad Soleimani",
            "text": "and if anyone new joins, it will give them a label. For example, if someone joins later"
            },
            {
            "start": 156.05,
            "end": 163.57,
            "speaker": "Farshad Soleimani",
            "text": "to the meeting, they would also have the assignments. We also discussed about test automation"
            },
            {
            "start": 163.65,
            "end": 171.65,
            "speaker": "Farshad Soleimani",
            "text": "and we evaluated the tests, but we thought that a live meeting assistant would be more"
            },
            {
            "start": 171.65,
            "end": 175.33,
            "speaker": "Farshad Soleimani",
            "text": "of a data science project than something to think about."
            },
            {
            "start": 175.68,
            "end": 182.4,
            "speaker": "Johannes Wowra",
            "text": "yeah okay can you go back sorry can you go back so so basically you have um uh so when you say"
            },
            {
            "start": 183.36,
            "end": 189.68,
            "speaker": "Johannes Wowra",
            "text": "meeting so this is the the the audio recording yeah right okay yes so the audio recording you"
            },
            {
            "start": 189.68,
            "end": 196.32,
            "speaker": "Johannes Wowra",
            "text": "do voice and uh voice recognition speech to text um and did you think also about speaker recognition"
            },
            {
            "start": 197.52,
            "end": 206.32000000000002,
            "speaker": "Farshad Soleimani",
            "text": "Yes, we already talked about that. It's the difference between the speakers and as I said,"
            },
            {
            "start": 197.76,
            "end": 198.26,
            "speaker": "Farshad Soleimani",
            "text": "Yes."
            },
            {
            "start": 198.26,
            "end": 198.76,
            "speaker": "Farshad Soleimani",
            "text": "Yes."
            },
            {
            "start": 198.76,
            "end": 199.26,
            "speaker": "Farshad Soleimani",
            "text": "Yes."
            },
            {
            "start": 207.12,
            "end": 215.12,
            "speaker": "Farshad Soleimani",
            "text": "as the input entry would give the different roles so we can decide which speaker has which role and"
            },
            {
            "start": 215.76000000000002,
            "end": 217.92000000000002,
            "speaker": "Farshad Soleimani",
            "text": "it will be trained on the voices."
            },
            {
            "start": 217.92000000000002,
            "end": 218.42000000000002,
            "speaker": "Farshad Soleimani",
            "text": "Okay."
            },
            {
            "start": 220.84,
            "end": 222.68,
            "speaker": "Farshad Soleimani",
            "text": "Yeah, okay, go on."
            },
            {
            "start": 222.68,
            "end": 229.64000000000001,
            "speaker": "Farshad Soleimani",
            "text": "So we have finally decided on this one and I think I already mentioned this slide."
            },
            {
            "start": 229.64000000000001,
            "end": 239.64000000000001,
            "speaker": "Farshad Soleimani",
            "text": "Yes, we can, as I said, we want, I think, for now, we want to make it any"
            },
            {
            "start": 239.64000000000001,
            "end": 245.8,
            "speaker": "Farshad Soleimani",
            "text": "difficult, but if you had free, if you were free or we had free time on the end,"
            },
            {
            "start": 246.52,
            "end": 254.68,
            "speaker": "Farshad Soleimani",
            "text": "we can decide if we use our own software, we make it a software or just an alternation"
            },
            {
            "start": 255.4,
            "end": 262.52,
            "speaker": "Farshad Soleimani",
            "text": "like Jamie, and we have discussed on building an user interface as it was."
            },
            {
            "start": 265.51,
            "end": 274.51,
            "speaker": "Farshad Soleimani",
            "text": "between ourselves, and I agree that Tavio would make the frontend and you the interface."
            },
            {
            "start": 274.51,
            "end": 276.51,
            "speaker": "Farshad Soleimani",
            "text": "Mm-hmm. That's the order."
            },
            {
            "start": 276.33,
            "end": 277.53,
            "speaker": "Safa V Abdul Ravuf",
            "text": "No, no, that was her."
            },
            {
            "start": 277.53,
            "end": 278.53,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Oh, it's okay, sorry."
            },
            {
            "start": 279.23,
            "end": 283.23,
            "speaker": "Farshad Soleimani",
            "text": "Okay, so this was okay. Yeah."
            },
            {
            "start": 283.23,
            "end": 287.23,
            "speaker": "Farshad Soleimani",
            "text": "And for now, I will make the repository."
            },
            {
            "start": 287.23,
            "end": 290.23,
            "speaker": "Farshad Soleimani",
            "text": "And that is just a matter of seconds."
            },
            {
            "start": 290.23,
            "end": 293.23,
            "speaker": "Farshad Soleimani",
            "text": "And I will control this."
            },
            {
            "start": 293.23,
            "end": 295.23,
            "speaker": "Farshad Soleimani",
            "text": "We have OpenAI."
            },
            {
            "start": 295.23,
            "end": 298.23,
            "speaker": "Farshad Soleimani",
            "text": "I think we had two APIs."
            },
            {
            "start": 298.23,
            "end": 303.23,
            "speaker": "Farshad Soleimani",
            "text": "One for the OpenAI API and one for Fisher Trello API."
            },
            {
            "start": 303.23,
            "end": 307.23,
            "speaker": "Farshad Soleimani",
            "text": "Or I think Trello would be fine."
            },
            {
            "start": 307.23,
            "end": 311.23,
            "speaker": "Farshad Soleimani",
            "text": "Or we would use Gmail API."
            },
            {
            "start": 311.23,
            "end": 313.23,
            "speaker": "Farshad Soleimani",
            "text": "So you could send an email."
            },
            {
            "start": 313.23,
            "end": 315.23,
            "speaker": "Farshad Soleimani",
            "text": "Okay."
            },
            {
            "start": 315.23,
            "end": 318.23,
            "speaker": "Farshad Soleimani",
            "text": "So what is OpenAI task generation? What is this?"
            },
            {
            "start": 318.23,
            "end": 323.23,
            "speaker": "Farshad Soleimani",
            "text": "It will generate the tasks from the transcripts."
            },
            {
            "start": 323.23,
            "end": 325.23,
            "speaker": "Farshad Soleimani",
            "text": "Okay, okay."
            },
            {
            "start": 324.87,
            "end": 325.71,
            "speaker": "Johannes Wowra",
            "text": "Okay, okay, okay."
            },
            {
            "start": 325.23,
            "end": 330.23,
            "speaker": "Farshad Soleimani",
            "text": "From what the project is and assign them to members."
            },
            {
            "start": 330.34,
            "end": 330.97999999999996,
            "speaker": "Johannes Wowra",
            "text": "Okay, so you..."
            },
            {
            "start": 331.03,
            "end": 339.66999999999996,
            "speaker": "Johannes Wowra",
            "text": "basically so this is yeah yeah maybe just as a maybe a diagram would make"
            },
            {
            "start": 339.66999999999996,
            "end": 342.95,
            "speaker": "Johannes Wowra",
            "text": "sense like that that shows what exactly like you have in the beginning you have"
            },
            {
            "start": 342.95,
            "end": 347.78999999999996,
            "speaker": "Johannes Wowra",
            "text": "audio right yes"
            },
            {
            "start": 346.22,
            "end": 347.46000000000004,
            "speaker": "Farshad Soleimani",
            "text": "Hello, how are you?"
            },
            {
            "start": 347.46000000000004,
            "end": 347.96000000000004,
            "speaker": "Farshad Soleimani",
            "text": "Good."
            },
            {
            "start": 347.96000000000004,
            "end": 349.5,
            "speaker": "Farshad Soleimani",
            "text": "Good to be in."
            },
            {
            "start": 348.42,
            "end": 350.42,
            "speaker": "Johannes Wowra",
            "text": "Yes, we can hear you a bit lower."
            },
            {
            "start": 350.59,
            "end": 351.09,
            "speaker": "Farshad Soleimani",
            "text": "What can you do?"
            },
            {
            "start": 351.09,
            "end": 353.09,
            "speaker": "Farshad Soleimani",
            "text": "I think the noise is better for that"
            },
            {
            "start": 353.48999999999995,
            "end": 353.98999999999995,
            "speaker": "Farshad Soleimani",
            "text": "What?"
            },
            {
            "start": 353.98999999999995,
            "end": 359.09,
            "speaker": "Farshad Soleimani",
            "text": "It's noisy and your voice is a little bit loud"
            },
            {
            "start": 359.09,
            "end": 360.09,
            "speaker": "Farshad Soleimani",
            "text": "No, it's not"
            },
            {
            "start": 360.03,
            "end": 367.30999999999995,
            "speaker": "Johannes Wowra",
            "text": "Okay, but I think I think it's like a moment moving word already talked about us through so let's let's just continue"
            },
            {
            "start": 367.98999999999995,
            "end": 373.15,
            "speaker": "Johannes Wowra",
            "text": "So and you're saying that's the so for open AI task generation"
            },
            {
            "start": 373.15,
            "end": 376.30999999999995,
            "speaker": "Johannes Wowra",
            "text": "That's basically so what I what I was what I would see man"
            },
            {
            "start": 376.30999999999995,
            "end": 379.83,
            "speaker": "Johannes Wowra",
            "text": "Maybe that will help you guys as well if you create kind of"
            },
            {
            "start": 381.75,
            "end": 389.10999999999996,
            "speaker": "Johannes Wowra",
            "text": "Kind of a flow diagram basically, we'll say okay you have the I mean on the one hand you will have the the audio, right?"
            },
            {
            "start": 389.46999999999997,
            "end": 391.98999999999995,
            "speaker": "Johannes Wowra",
            "text": "That will be that will be detected then you need to do"
            },
            {
            "start": 393.59,
            "end": 399.03,
            "speaker": "Johannes Wowra",
            "text": "Some basically the voice recognition part right that has to be done out of that you have"
            },
            {
            "start": 399.78999999999996,
            "end": 406.27,
            "speaker": "Johannes Wowra",
            "text": "Probably multiple outputs because one output would be okay. You will have you will have the transcript you will have"
            },
            {
            "start": 406.95,
            "end": 409.34999999999997,
            "speaker": "Johannes Wowra",
            "text": "the amount of speakers right"
            },
            {
            "start": 409.77,
            "end": 417.34999999999997,
            "speaker": "Johannes Wowra",
            "text": "You will have also I mean you would probably also have the I guess so this is still so probably on the"
            },
            {
            "start": 417.34999999999997,
            "end": 422.13,
            "speaker": "Johannes Wowra",
            "text": "I get on the audio level. There's some quite some work because you need to you have the you have the"
            },
            {
            "start": 422.60999999999996,
            "end": 425.89,
            "speaker": "Johannes Wowra",
            "text": "The audio file then then basically when you do the voice recognition"
            },
            {
            "start": 425.89,
            "end": 430.96999999999997,
            "speaker": "Johannes Wowra",
            "text": "You will detect all the pieces that have voice and then those voice pieces will be then also"
            },
            {
            "start": 432.09,
            "end": 436.37,
            "speaker": "Johannes Wowra",
            "text": "Separated into into different speakers, right? And then you would have speaker a"
            },
            {
            "start": 434.04,
            "end": 434.54,
            "speaker": "Johannes Wowra",
            "text": "Right?"
            },
            {
            "start": 437.28999999999996,
            "end": 444.01,
            "speaker": "Johannes Wowra",
            "text": "Doing audio script speaker the audio script and then you have to basically also do like the and then you do the transcript"
            },
            {
            "start": 444.01,
            "end": 448.51,
            "speaker": "Johannes Wowra",
            "text": "Right, so getting the audio scripts into into the whatever was was said, right?"
            },
            {
            "start": 450.01,
            "end": 456.77,
            "speaker": "Johannes Wowra",
            "text": "Okay, and then that's basically the input for for the open AI task generation, right? Yes"
            },
            {
            "start": 457.45,
            "end": 462.13,
            "speaker": "Johannes Wowra",
            "text": "So I think so it's basically two kind of two if you take the whole project"
            },
            {
            "start": 462.13,
            "end": 468.92999999999995,
            "speaker": "Johannes Wowra",
            "text": "It's too too many projects like not many but two different projects within this one, right? So one will be about voice recognition"
            },
            {
            "start": 469.77,
            "end": 473.37,
            "speaker": "Johannes Wowra",
            "text": "transcription and then speaker recognition"
            },
            {
            "start": 474.28999999999996,
            "end": 477.69,
            "speaker": "Johannes Wowra",
            "text": "From the voice of the right and fashion what you are writing. Yes"
            },
            {
            "start": 477.69,
            "end": 482.13,
            "speaker": "Johannes Wowra",
            "text": "I think I think it's definitely is probably essential to understand the different speakers"
            },
            {
            "start": 482.69,
            "end": 488.96999999999997,
            "speaker": "Johannes Wowra",
            "text": "The I guess what your question points to is if you need to do that from the voice or if you want to of you"
            },
            {
            "start": 488.96999999999997,
            "end": 490.89,
            "speaker": "Johannes Wowra",
            "text": "If I can do that, right?"
            },
            {
            "start": 490.89,
            "end": 496.53,
            "speaker": "Johannes Wowra",
            "text": "So I think it's I mean if you want a better quality, I think if you should do that on the on the audio level and"
            },
            {
            "start": 496.53,
            "end": 498.53,
            "speaker": "Johannes Wowra",
            "text": "detected speakers"
            },
            {
            "start": 497.69,
            "end": 501.13,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Yeah, because we did look for this voice recognition"
            },
            {
            "start": 501.13,
            "end": 503.69,
            "speaker": "Safa V Abdul Ravuf",
            "text": "and we saw that there were some softwares that did help us,"
            },
            {
            "start": 503.69,
            "end": 506.21,
            "speaker": "Safa V Abdul Ravuf",
            "text": "but then we were thinking that we could actually"
            },
            {
            "start": 506.21,
            "end": 508.53,
            "speaker": "Safa V Abdul Ravuf",
            "text": "create a model or something because..."
            },
            {
            "start": 508.41,
            "end": 511.21000000000004,
            "speaker": "Johannes Wowra",
            "text": "That's, I mean, that's pretty, I mean, yeah."
            },
            {
            "start": 509.32,
            "end": 510.86,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Yeah."
            },
            {
            "start": 511.43,
            "end": 514.07,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Would that be better without discussing it?"
            },
            {
            "start": 514.31,
            "end": 516.7099999999999,
            "speaker": "Johannes Wowra",
            "text": "if you would create a model and set off."
            },
            {
            "start": 516.86,
            "end": 520.22,
            "speaker": "Safa V Abdul Ravuf",
            "text": "instead of using weighted CS software called OpenAI Whisper."
            },
            {
            "start": 520.69,
            "end": 526.1300000000001,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Yeah, it did say, I mean, according to what I just read a brief description,"
            },
            {
            "start": 526.1300000000001,
            "end": 529.57,
            "speaker": "Safa V Abdul Ravuf",
            "text": "it was said that it would help us with the voice recognition."
            },
            {
            "start": 529.99,
            "end": 534.23,
            "speaker": "Safa V Abdul Ravuf",
            "text": "at us, but then we were actually, we thought maybe if we could."
            },
            {
            "start": 534.83,
            "end": 540.35,
            "speaker": "Safa V Abdul Ravuf",
            "text": "develop a model then a bit more of that we could like have hands-on experience with data science."
            },
            {
            "start": 540.59,
            "end": 546.51,
            "speaker": "Johannes Wowra",
            "text": "yeah sure i mean yeah i mean that's uh i mean voice and speaker recognition is a very classical"
            },
            {
            "start": 546.51,
            "end": 549.87,
            "speaker": "Johannes Wowra",
            "text": "uh data science task so um"
            },
            {
            "start": 550.43,
            "end": 552.43,
            "speaker": "Safa V Abdul Ravuf",
            "text": "What would be your suggestion?"
            },
            {
            "start": 552.84,
            "end": 559.76,
            "speaker": "Johannes Wowra",
            "text": "The thing is, obviously, I mean, if you're using, I think, nowadays, and I compared with"
            },
            {
            "start": 559.76,
            "end": 565.1600000000001,
            "speaker": "Johannes Wowra",
            "text": "when I also, when I was in the TU Darmstadt, I had also lectures about voice and speaker"
            },
            {
            "start": 565.1600000000001,
            "end": 566.1600000000001,
            "speaker": "Johannes Wowra",
            "text": "recognition."
            },
            {
            "start": 566.1600000000001,
            "end": 570.2,
            "speaker": "Johannes Wowra",
            "text": "And at that time, it was a bit of a more challenging problem."
            },
            {
            "start": 570.2,
            "end": 576.1600000000001,
            "speaker": "Johannes Wowra",
            "text": "I think nowadays, it's a very standard, probably solved problem."
            },
            {
            "start": 576.1600000000001,
            "end": 581.32,
            "speaker": "Johannes Wowra",
            "text": "So I mean, I think with the libraries today, you can easily train a model."
            },
            {
            "start": 581.32,
            "end": 586.2,
            "speaker": "Johannes Wowra",
            "text": "But the problem is, I mean, you would have to take like a base model, right?"
            },
            {
            "start": 585.36,
            "end": 586.9,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Yeah."
            },
            {
            "start": 586.2,
            "end": 589.32,
            "speaker": "Johannes Wowra",
            "text": "So you would not train a model from scratch."
            },
            {
            "start": 589.32,
            "end": 600.28,
            "speaker": "Johannes Wowra",
            "text": "So with the base models, I assume that you would get a decent speaker recognition already."
            },
            {
            "start": 600.28,
            "end": 606.4000000000001,
            "speaker": "Johannes Wowra",
            "text": "So you can also, I mean, you can try with libraries in the beginning and see how good"
            },
            {
            "start": 606.4000000000001,
            "end": 607.4000000000001,
            "speaker": "Johannes Wowra",
            "text": "it is."
            },
            {
            "start": 607.4000000000001,
            "end": 613.2,
            "speaker": "Johannes Wowra",
            "text": "And maybe if you want, fine tune it with your own voices, for example, right?"
            },
            {
            "start": 613.44,
            "end": 613.94,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Okay."
            },
            {
            "start": 613.94,
            "end": 615.86,
            "speaker": "Johannes Wowra",
            "text": "That might be something that helps."
            },
            {
            "start": 615.86,
            "end": 618.8000000000001,
            "speaker": "Johannes Wowra",
            "text": "But I think this is something that should be,"
            },
            {
            "start": 618.8000000000001,
            "end": 620.74,
            "speaker": "Johannes Wowra",
            "text": "I would assume that the results would be decent"
            },
            {
            "start": 620.74,
            "end": 622.98,
            "speaker": "Johannes Wowra",
            "text": "with existing libraries already."
            },
            {
            "start": 622.98,
            "end": 625.58,
            "speaker": "Johannes Wowra",
            "text": "I mean, I did it recently for,"
            },
            {
            "start": 625.58,
            "end": 628.94,
            "speaker": "Johannes Wowra",
            "text": "I did like audio transcription with a library, it was okay."
            },
            {
            "start": 628.94,
            "end": 630.9000000000001,
            "speaker": "Johannes Wowra",
            "text": "It was not perfect, definitely,"
            },
            {
            "start": 630.9000000000001,
            "end": 633.86,
            "speaker": "Johannes Wowra",
            "text": "but that's like, the audio transcription will give you,"
            },
            {
            "start": 633.86,
            "end": 637.1800000000001,
            "speaker": "Johannes Wowra",
            "text": "let's say kind of a 90% text, right?"
            },
            {
            "start": 637.1800000000001,
            "end": 639.5,
            "speaker": "Johannes Wowra",
            "text": "And 10% gibberish, maybe,"
            },
            {
            "start": 639.5,
            "end": 642.82,
            "speaker": "Johannes Wowra",
            "text": "but then the AI compensates for this."
            },
            {
            "start": 643.74,
            "end": 646.34,
            "speaker": "Johannes Wowra",
            "text": "So that's, I think that's for you guys to find out"
            },
            {
            "start": 646.34,
            "end": 648.6800000000001,
            "speaker": "Johannes Wowra",
            "text": "what's the trade-off, right?"
            },
            {
            "start": 648.6800000000001,
            "end": 651.5400000000001,
            "speaker": "Johannes Wowra",
            "text": "So where do we, where can we,"
            },
            {
            "start": 651.5400000000001,
            "end": 654.4200000000001,
            "speaker": "Johannes Wowra",
            "text": "where should we invest time into developing a better model"
            },
            {
            "start": 654.4200000000001,
            "end": 656.82,
            "speaker": "Johannes Wowra",
            "text": "or use AI for this, right?"
            },
            {
            "start": 656.82,
            "end": 661.82,
            "speaker": "Johannes Wowra",
            "text": "This is also, this is a problem of investment and effort,"
            },
            {
            "start": 662.5,
            "end": 663.6600000000001,
            "speaker": "Johannes Wowra",
            "text": "but also on the other hand,"
            },
            {
            "start": 663.6600000000001,
            "end": 666.6600000000001,
            "speaker": "Johannes Wowra",
            "text": "it's a problem of cost, obviously, right?"
            },
            {
            "start": 666.6600000000001,
            "end": 670.1,
            "speaker": "Johannes Wowra",
            "text": "So training your own model and having a local model"
            },
            {
            "start": 670.1,
            "end": 672.98,
            "speaker": "Johannes Wowra",
            "text": "to detect the speakers is way cheaper, right?"
            },
            {
            "start": 672.98,
            "end": 675.6600000000001,
            "speaker": "Johannes Wowra",
            "text": "Than calling the AI for this every time."
            },
            {
            "start": 675.6600000000001,
            "end": 677.82,
            "speaker": "Johannes Wowra",
            "text": "But that's, I think, something that you would need"
            },
            {
            "start": 677.82,
            "end": 679.4200000000001,
            "speaker": "Johannes Wowra",
            "text": "to experiment and then decide."
            },
            {
            "start": 679.4200000000001,
            "end": 680.2600000000001,
            "speaker": "Johannes Wowra",
            "text": "Okay."
            },
            {
            "start": 680.2600000000001,
            "end": 683.72,
            "speaker": "Johannes Wowra",
            "text": "That's your, I mean, so I would try with existing libraries"
            },
            {
            "start": 683.72,
            "end": 684.86,
            "speaker": "Johannes Wowra",
            "text": "and see how the performance is."
            },
            {
            "start": 684.86,
            "end": 687.34,
            "speaker": "Johannes Wowra",
            "text": "You always, when you do those things,"
            },
            {
            "start": 687.34,
            "end": 690.2600000000001,
            "speaker": "Johannes Wowra",
            "text": "always think about how to evaluate it, right?"
            },
            {
            "start": 690.2600000000001,
            "end": 692.34,
            "speaker": "Johannes Wowra",
            "text": "So when you do the voice recognition,"
            },
            {
            "start": 692.34,
            "end": 695.0,
            "speaker": "Johannes Wowra",
            "text": "always think about how can we evaluate this"
            },
            {
            "start": 695.0,
            "end": 698.7,
            "speaker": "Johannes Wowra",
            "text": "so that we know how good it is, right?"
            },
            {
            "start": 698.7,
            "end": 700.6200000000001,
            "speaker": "Johannes Wowra",
            "text": "So, I mean, for voice recognition,"
            },
            {
            "start": 700.6200000000001,
            "end": 703.2600000000001,
            "speaker": "Johannes Wowra",
            "text": "probably you would need some kind of test data."
            },
            {
            "start": 703.97,
            "end": 708.97,
            "speaker": "Johannes Wowra",
            "text": "I guess you will not, I mean, it will probably take too much time to generate it yourself."
            },
            {
            "start": 708.97,
            "end": 715.97,
            "speaker": "Johannes Wowra",
            "text": "So there will be test datasets where you can download audio files with people and then the correct transcripts."
            },
            {
            "start": 715.97,
            "end": 718.97,
            "speaker": "Johannes Wowra",
            "text": "So you can do the images on this."
            },
            {
            "start": 718.97,
            "end": 722.97,
            "speaker": "Johannes Wowra",
            "text": "Okay, sorry, I'm looking at the time. I have only four minutes there."
            },
            {
            "start": 722.97,
            "end": 728.97,
            "speaker": "Johannes Wowra",
            "text": "So I think we should try to be more organized for the next time."
            },
            {
            "start": 728.97,
            "end": 731.97,
            "speaker": "Johannes Wowra",
            "text": "So it's..."
            },
            {
            "start": 732.03,
            "end": 740.8299999999999,
            "speaker": "Farshad Soleimani",
            "text": "I have no problem at all, by the present form, I think it is even better, but just I saw the email."
            },
            {
            "start": 740.89,
            "end": 747.37,
            "speaker": "Johannes Wowra",
            "text": "I'm fine with either. I'm prepared for both. I will be here in this meeting room and I will be"
            },
            {
            "start": 747.37,
            "end": 754.89,
            "speaker": "Johannes Wowra",
            "text": "connected to the team so I'm fine if you join online or remote. Just that let's try to be on"
            },
            {
            "start": 754.89,
            "end": 761.45,
            "speaker": "Johannes Wowra",
            "text": "time and and also yes okay anyway uh so what what else do we have on the list we have um"
            },
            {
            "start": 762.5699999999999,
            "end": 765.45,
            "speaker": "Johannes Wowra",
            "text": "the other product engineering"
            },
            {
            "start": 763.96,
            "end": 772.0400000000001,
            "speaker": "Farshad Soleimani",
            "text": "that's just part of the API for the opening and we are finding new, which is the important part"
            },
            {
            "start": 772.84,
            "end": 783.32,
            "speaker": "Farshad Soleimani",
            "text": "and we have N18, one of us will be in charge for having the account and the rest of us I think"
            },
            {
            "start": 783.32,
            "end": 789.32,
            "speaker": "Farshad Soleimani",
            "text": "it's good that the rest of us have the experience with N18 too because as the final part only one"
            },
            {
            "start": 789.32,
            "end": 790.9200000000001,
            "speaker": "Farshad Soleimani",
            "text": "person manage"
            },
            {
            "start": 792.03,
            "end": 796.53,
            "speaker": "Johannes Wowra",
            "text": "Yeah, so I can I will give you access to this. I'm still in contact with"
            },
            {
            "start": 798.05,
            "end": 799.17,
            "speaker": "Johannes Wowra",
            "text": "Tommy"
            },
            {
            "start": 799.17,
            "end": 804.47,
            "speaker": "Johannes Wowra",
            "text": "So I will get I'll get that for you guys and to your question"
            },
            {
            "start": 804.99,
            "end": 807.4499999999999,
            "speaker": "Johannes Wowra",
            "text": "For sure. I mean, it's you guys have to"
            },
            {
            "start": 807.97,
            "end": 814.63,
            "speaker": "Johannes Wowra",
            "text": "I think what the first thing that you would need to do is and this is basically for because you have a bit of different"
            },
            {
            "start": 815.17,
            "end": 816.2099999999999,
            "speaker": "Johannes Wowra",
            "text": "different"
            },
            {
            "start": 816.2099999999999,
            "end": 818.93,
            "speaker": "Johannes Wowra",
            "text": "tasks so the one is the voice recognition the other one is the"
            },
            {
            "start": 819.67,
            "end": 823.37,
            "speaker": "Johannes Wowra",
            "text": "Anything that is related to the prompt engineering and and the task generation"
            },
            {
            "start": 823.37,
            "end": 829.63,
            "speaker": "Johannes Wowra",
            "text": "So I would recommend you guys that you sit together and you define the tasks that are needed and then"
            },
            {
            "start": 830.73,
            "end": 831.89,
            "speaker": "Johannes Wowra",
            "text": "basically"
            },
            {
            "start": 831.89,
            "end": 836.89,
            "speaker": "Johannes Wowra",
            "text": "Try to so what you usually do is also try to effort estimate those tasks, right?"
            },
            {
            "start": 836.89,
            "end": 842.8299999999999,
            "speaker": "Johannes Wowra",
            "text": "So see, okay, we have I don't know. There's a task of setting up setting up GitHub. That's something that's five minutes"
            },
            {
            "start": 842.8299999999999,
            "end": 848.49,
            "speaker": "Johannes Wowra",
            "text": "Right, but then there is a task of speaker recognition, right that will take that will take longer"
            },
            {
            "start": 848.49,
            "end": 852.3299999999999,
            "speaker": "Johannes Wowra",
            "text": "so try to and this is this is also a group thing that you should do try to"
            },
            {
            "start": 853.17,
            "end": 857.89,
            "speaker": "Johannes Wowra",
            "text": "Write down all the tasks and then try to find more or less. They don't have to be exact"
            },
            {
            "start": 858.41,
            "end": 862.3299999999999,
            "speaker": "Johannes Wowra",
            "text": "Sometimes it's enough if you do t-shirt sizing so you say it's an S and M or L"
            },
            {
            "start": 862.3299999999999,
            "end": 866.51,
            "speaker": "Johannes Wowra",
            "text": "Right, and if you know that then you can then you can start distributing the task properly"
            },
            {
            "start": 866.68,
            "end": 869.12,
            "speaker": "Safa V Abdul Ravuf",
            "text": "You know, according to this task distribution,"
            },
            {
            "start": 869.12,
            "end": 872.12,
            "speaker": "Safa V Abdul Ravuf",
            "text": "four people are for voice recognition."
            },
            {
            "start": 872.12,
            "end": 873.0,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Yeah."
            },
            {
            "start": 873.0,
            "end": 877.3599999999999,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Do you think we need more or is like four people needed?"
            },
            {
            "start": 877.29,
            "end": 882.73,
            "speaker": "Johannes Wowra",
            "text": "that that's why i'm saying so i don't honestly i don't i don't know i don't think it's i mean"
            },
            {
            "start": 882.73,
            "end": 887.61,
            "speaker": "Johannes Wowra",
            "text": "four people is uh maybe maybe too much because you have also on the everything that is if you"
            },
            {
            "start": 887.61,
            "end": 893.4499999999999,
            "speaker": "Johannes Wowra",
            "text": "go to slide five so right so everything that is on the right side this is also i mean this is also"
            },
            {
            "start": 893.4499999999999,
            "end": 897.6899999999999,
            "speaker": "Johannes Wowra",
            "text": "probably a lot of effort to do those things basically to do the to the right the right"
            },
            {
            "start": 897.6899999999999,
            "end": 903.61,
            "speaker": "Johannes Wowra",
            "text": "prompts to come up with uh with ideas how to extract how to extract tasks from text yes right"
            },
            {
            "start": 903.61,
            "end": 910.89,
            "speaker": "Johannes Wowra",
            "text": "how to um um how to do the role mapping and then things that you have planned right so this is um"
            },
            {
            "start": 910.89,
            "end": 914.9699999999999,
            "speaker": "Johannes Wowra",
            "text": "so as i said i think you have to you have to sit down and write down all the tasks and all"
            },
            {
            "start": 914.9699999999999,
            "end": 920.25,
            "speaker": "Johannes Wowra",
            "text": "the areas that you want to that you want to focus on and also define um and this will also help you"
            },
            {
            "start": 920.25,
            "end": 924.41,
            "speaker": "Johannes Wowra",
            "text": "to define what the application is capable what the application features are and then and then"
            },
            {
            "start": 924.41,
            "end": 925.6899999999999,
            "speaker": "Johannes Wowra",
            "text": "you can distribute the tasks"
            },
            {
            "start": 925.69,
            "end": 929.69,
            "speaker": "Safa V Abdul Ravuf",
            "text": "So it would be better that we create a list of all the tasks that had to be done."
            },
            {
            "start": 929.89,
            "end": 931.89,
            "speaker": "Johannes Wowra",
            "text": "I mean, not in super detail, right?"
            },
            {
            "start": 931.38,
            "end": 937.54,
            "speaker": "Safa V Abdul Ravuf",
            "text": "Yeah, but then approximate first and then assign people accordingly."
            },
            {
            "start": 937.42,
            "end": 941.0999999999999,
            "speaker": "Johannes Wowra",
            "text": "Right. I mean, you will also have different skills, right?"
            },
            {
            "start": 941.0999999999999,
            "end": 941.6999999999999,
            "speaker": "Johannes Wowra",
            "text": "Yes."
            },
            {
            "start": 941.6999999999999,
            "end": 944.6999999999999,
            "speaker": "Johannes Wowra",
            "text": "So some people are more into the UI."
            },
            {
            "start": 944.6999999999999,
            "end": 947.74,
            "speaker": "Johannes Wowra",
            "text": "I mean, I thought, for example, the UI part is not..."
            },
            {
            "start": 947.74,
            "end": 949.3399999999999,
            "speaker": "Johannes Wowra",
            "text": "Did you mention that somewhere?"
            },
            {
            "start": 949.3399999999999,
            "end": 950.8199999999999,
            "speaker": "Johannes Wowra",
            "text": "Because that will be also..."
            },
            {
            "start": 950.8199999999999,
            "end": 954.02,
            "speaker": "Johannes Wowra",
            "text": "I mean, how do you envision a UI, right?"
            },
            {
            "start": 954.02,
            "end": 956.2199999999999,
            "speaker": "Johannes Wowra",
            "text": "I mean, UI can be just a simple window"
            },
            {
            "start": 956.2199999999999,
            "end": 959.06,
            "speaker": "Johannes Wowra",
            "text": "or it can be super complex platform, right?"
            },
            {
            "start": 959.06,
            "end": 962.9,
            "speaker": "Johannes Wowra",
            "text": "So that's what I think you still need to define"
            },
            {
            "start": 962.9,
            "end": 965.62,
            "speaker": "Johannes Wowra",
            "text": "so that you have a clear picture of what the effort is."
            },
            {
            "start": 965.62,
            "end": 966.06,
            "speaker": "Johannes Wowra",
            "text": "Okay."
            },
            {
            "start": 966.06,
            "end": 967.86,
            "speaker": "Johannes Wowra",
            "text": "Okay. I'm so sorry."
            },
            {
            "start": 967.86,
            "end": 969.14,
            "speaker": "Johannes Wowra",
            "text": "I need to go to the next meeting."
            },
            {
            "start": 969.14,
            "end": 969.74,
            "speaker": "Johannes Wowra",
            "text": "Okay."
            },
            {
            "start": 970.62,
            "end": 973.8199999999999,
            "speaker": "Johannes Wowra",
            "text": "So we have the time for next week"
            },
            {
            "start": 973.8199999999999,
            "end": 975.54,
            "speaker": "Johannes Wowra",
            "text": "and I think next week I have also an hour..."
            },
            {
            "start": 975.54,
            "end": 976.74,
            "speaker": "Johannes Wowra",
            "text": "Oh, no. Wait."
            }
        ],
        "profiles": [
            {
            "id": "trello-691cfb6877a5455b0f060b6b",
            "name": "Adarsh Haridas",
            "trello_id": "691cfb6877a5455b0f060b6b",
            "trello_username": "adarshharidas2",
            "email": "adarsh.haridas@stud.tu-darmstadt.de",
            "role": "AI Engineer",
            "skills": [
                "Python",
                "Voice Recognition",
                "Data Analysis",
                "Machine Learning"
            ],
            "notes": "I am experienced in AI engineering and have a strong background in Python, voice recognition, data analysis, and machine learning.",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-691cfe3cd850a0c7e050fb0c",
            "name": "Ananthu Vijayan",
            "trello_id": "691cfe3cd850a0c7e050fb0c",
            "trello_username": "ananthuvijayan2",
            "email": "ananthu.vijayan@stud.tu-darmstadt.de",
            "role": "Voice Recognition Specialist",
            "skills": [
                "Python",
                "Voice Recognition",
                "Data Analysis"
            ],
            "notes": "I am experienced in voice recognition and data analysis. I enjoy working with audio data and extracting meaningful insights.",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-691d6957f31278bc04161b86",
            "name": "CHRISTINE MATHEW VATHIYATH MATHAI",
            "trello_id": "691d6957f31278bc04161b86",
            "trello_username": "christinemathewvathiyathmathai",
            "email": "christinemathewvm@gmail.com",
            "role": "Audio Transcription Specialist",
            "skills": [
                "Python",
                "Data Science",
                "Microsoft PowerPoint"
            ],
            "notes": "I like to learn new skills and interested in exploring advancements in technology.",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-691dc049bee1daebfa96ccdb",
            "name": "Farshad Soleimani",
            "trello_id": "691dc049bee1daebfa96ccdb",
            "trello_username": "farshadsoleimani3",
            "email": "",
            "role": "Project Coordinator, n8n Automation Engineer",
            "skills": [
                "n8n",
                "Python",
                "Mcrosoft Project",
                "Trello"
            ],
            "notes": "I am good at time managememt, and I am sociable and eager to learn new things. I like the roles related to applicable softwares which have broad usages.",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-6926238add3cf015343d72ad",
            "name": "Johannes Wowra",
            "trello_id": "6926238add3cf015343d72ad",
            "trello_username": "johanneswowra2",
            "email": "",
            "role": "Project Supervisor",
            "skills": [
                "Management",
                "Leadership",
                "Communication"
            ],
            "notes": "I have experience in project management and team leadership. I am passionate about guiding teams to success and ensuring effective communication among members.",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-691cde56cb97a82831ddf2df",
            "name": "Mobin",
            "trello_id": "691cde56cb97a82831ddf2df",
            "trello_username": "mobin148",
            "email": "mobin.liaghi@gmail.com",
            "role": "n8n Automation Engineer",
            "skills": [
                "Python",
                "n8n",
                "API",
                "Microsoft PowerPoint"
            ],
            "notes": "I love being in order, learn new things specifically the things related to computer technologies.",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-691cfa215ae73978990743f6",
            "name": "Safa V Abdul Ravuf",
            "trello_id": "691cfa215ae73978990743f6",
            "trello_username": "safavabdulravuf",
            "email": "safaravuf98@gmail.com",
            "role": "Information and Engineering Student",
            "skills": [
                "Python",
                "Data Science",
                "Machine Learning",
                "Speaker Diarization"
            ],
            "notes": "Organised, enthusisatic about learning new skills, expereince with software development",
            "photo": None,
            "status": "imported"
            },
            {
            "id": "trello-691cc9c0b8b51e2811fe2bf4",
            "name": "Tabia Karim",
            "trello_id": "691cc9c0b8b51e2811fe2bf4",
            "trello_username": "tabiakarim",
            "email": "tabia.karim@stud.tu-darmstadt.de",
            "role": "Frontend Developer",
            "skills": [
                "Python",
                "Streamlit",
                "C++",
                "ROS2",
                "Java"
            ],
            "notes": "A robotics student with an interest in Data Science and AI. I am eager to learn new skills and contribute to the team. My focus is on frontend development, but I am also interested in exploring other areas.",
            "photo": None,
            "status": "imported"
            }
        ]
    }

# -----------------------
# Very small helpers
# -----------------------
def post_start(meeting_id: str, payload: dict) -> tuple[bool, str]:
    url = f"{API_BASE}/n8n/{N8N_ROUTE_SECRET}/start/{meeting_id}"
    try:
        r = requests.post(url, json=payload, timeout=15)
    except Exception as e:
        return False, f"Network error: {e}"

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        return False, f"429 rate-limited. Retry-After={ra or 'n/a'} Body={r.text[:200]}"

    if not r.ok:
        return False, f"HTTP {r.status_code}: {r.text[:400]}"

    return True, r.text[:400] or "ok"

def get_status(meeting_id: str) -> tuple[bool, dict | str]:
    url = f"{API_BASE}/n8n/{N8N_ROUTE_SECRET}/status/{meeting_id}"
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        return False, f"Network error: {e}"

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        return False, f"429 rate-limited. Retry-After={ra or 'n/a'} Body={r.text[:200]}"

    if not r.ok:
        return False, f"HTTP {r.status_code}: {r.text[:400]}"

    try:
        return True, r.json()
    except Exception:
        return False, f"Bad JSON response: {r.text[:400]}"

# -----------------------
# Session state
# -----------------------
if "meeting_id" not in st.session_state:
    st.session_state.meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
if "sent" not in st.session_state:
    st.session_state.sent = False
if "result" not in st.session_state:
    st.session_state.result = None
if "last_start_ts" not in st.session_state:
    st.session_state.last_start_ts = 0.0
if "start_cooldown_s" not in st.session_state:
    st.session_state.start_cooldown_s = 5.0
if "last_status_ts" not in st.session_state:
    st.session_state.last_status_ts = 0.0
if "status_cooldown_s" not in st.session_state:
    st.session_state.status_cooldown_s = 5.0

# -----------------------
# UI
# -----------------------
c1, c2, c3 = st.columns([2, 1, 2])
with c1:
    st.session_state.meeting_id = st.text_input("Meeting ID", st.session_state.meeting_id).strip() or st.session_state.meeting_id
with c2:
    if st.button("New ID", use_container_width=True):
        st.session_state.meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
        st.session_state.sent = False
        st.session_state.result = None
        st.session_state.last_start_ts = 0.0  
        st.session_state.last_status_ts = 0.0
        st.rerun()
    
with c3:
    st.caption(f"Backend: {API_BASE}")

payload = build_demo_payload(st.session_state.meeting_id)

with st.expander("Payload preview", expanded=False):
    st.json(payload)

st.divider()

now = time.time()
start_remaining = max(0, int(st.session_state.start_cooldown_s - (now - st.session_state.last_start_ts)))
can_start = (start_remaining == 0) and (not st.session_state.sent)

send = st.button("Send to n8n", type="primary", use_container_width=True, disabled=not can_start)

if not can_start:
    if st.session_state.sent:
        st.info("Already sent for this Meeting ID. Click **New ID** to send again.")
    else:
        st.caption(f"Start cooldown: try again in {start_remaining}s")

if send:
    ok, msg = post_start(st.session_state.meeting_id, payload)
    if not ok:
        st.session_state.sent = False
        st.error(msg)
        st.stop()

    # ✅ only set cooldown timestamp after success
    st.session_state.last_start_ts = time.time()
    st.session_state.sent = True
    st.success("Sent ✅")

st.divider()

now = time.time()
status_remaining = max(0, int(st.session_state.status_cooldown_s - (now - st.session_state.last_status_ts)))
can_poll = st.session_state.sent and (status_remaining == 0)

refresh = st.button("Refresh status", use_container_width=True, disabled=not can_poll)

if st.session_state.sent and not can_poll:
    st.caption(f"Next status refresh in {status_remaining}s")

if refresh:
    ok, data = get_status(st.session_state.meeting_id)
    if not ok:
        st.error(data)
        st.stop()

    st.session_state.last_status_ts = time.time()  # ✅ after success

    latest = (data or {}).get("latest")
    result = (data or {}).get("result")

    st.subheader("Latest")
    st.json(latest or {})

    if result:
        st.subheader("Final result")
        st.session_state.result = result
        st.json(result)

if st.session_state.result and not refresh:
    st.subheader("Final result")
    st.json(st.session_state.result)
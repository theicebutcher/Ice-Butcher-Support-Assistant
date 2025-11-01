import os
import base64
from flask import Flask, render_template, request, jsonify
import openai
from dotenv import load_dotenv
import json
import gspread
from flask_cors import CORS

# Authenticate to Google Sheets API
gc = gspread.service_account(filename='avatarbobo-jqrl-a5a4668c4ba0.json') # Replace with the actual path to your service account credentials file

# Open the Google Sheet by title
sheet = gc.open_by_key('1AC_utnrgclGgm1xMkSW_APhVY9c-ORIzGrT7mu7fHdI') # Replace with your spreadsheet ID

# Select the worksheet (tab)
worksheet = sheet.sheet1 # Assuming you want to access the first worksheet

# Load FAQ data from a JSON file
# Load FAQ data from a JSON file with UTF-8 encoding


with open('faq.json', 'r', encoding='utf-8') as file:
    faq_data = json.load(file)

# # Create the custom prompt
# custom_prompt = f"""
# You are an AI assistant for an ice sculpture company named "Ice Butcher".
# This is the information and question answers you need to assist users based on this data:
# if user mentions order then show the order link otherwise dont show the order link. only show the required links, if all links are asked then skip the order link, only show order when asked explicitly.
# {json.dumps(faq_data, indent=2)}



# """




app = Flask(__name__)
CORS(app)
app.config["UPLOAD_FOLDER"] = "static/uploads"

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variable
api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=api_key)

# Function to encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Global conversation history with a welcome message
conversation_history = [{"user": "", "ai": "Welcome to Ice Butcher! How can I assist you today?  If you have any questions about ice sculptures or our services, feel free to ask.🧊"}]


@app.route("/", methods=["GET"])
def index():
    # Render the template and pass the initial conversation history
    return render_template("index.html", conversation_history=conversation_history)

# Load Images data
import json

def load_faq_data():
    with open('images2.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # Extract the list from the dictionary
    if isinstance(data, dict) and "standardSculptures" in data:
        return data["standardSculptures"]
    
    raise ValueError("Unexpected JSON structure. Expected 'standardSculptures' key.")

from rapidfuzz import process, fuzz


def find_top_matches(user_input, data):
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("Data should be a list of dictionaries.")

    # Extract names from data and store a reference dictionary
    choices = {item.get("name", "").lower(): item for item in data if "name" in item}

    # Use process.extract to get top 100 matches with optimized scoring
    matches = process.extract(user_input.lower(), choices.keys(), scorer=fuzz.QRatio, limit=100)

    # Return sorted list based on similarity score
    sorted_matches = [choices[match[0]] for match in matches]

    return sorted_matches  # Returns top 100 matches

conversation_history = []


def find_order_in_sheet(order_id):
# Retrieve all values from the worksheet
    data = worksheet.get_all_records()

# Search for the order_id in the data
    for row in data:
        if str(row.get("Order ID")) == order_id:  # Assuming your column is labeled "Order ID"
            return row

    return None

@app.route('/track_order', methods=['POST'])
def track_order():
    data = request.get_json()
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'error': 'Order ID is required'}), 400
    # Search for the order in Google Sheets
    order_data = find_order_in_sheet(order_id)

    if order_data:
        # If order is found, return the details
        return jsonify({
            'found': True,
            'order_id': order_id,
            'status': order_data.get('Status', 'N/A'),  # Replace 'Status' with your actual column name
            'details': order_data.get('Details', 'N/A')  # Replace 'Details' with your actual column name
        })
    else:
        # If order is not found, return an error message
        return jsonify({'found': False, 'message': 'Order not found'})

@app.route("/chatbot", methods=["POST"])
def chatbot():
    


    user_input = request.form.get("user_input", "").strip().lower()
    uploaded_file = request.files.get("image")

    try:
                # Load image data and find top matches
        image_data = load_faq_data()
        sorted_matches = find_top_matches(user_input, image_data)[:100]  # Get only the top 10 matches
        # print(json.dumps(sorted_matches, indent=2, ensure_ascii=False))

        # Create the custom prompt with matched results
        custom_prompt = f"""
        You are an AI assistant for an ice sculpture company named "Ice Butcher".
        This is the information and question answers you need to assist users based on this data:
        If user mentions order then show the order link, otherwise don't show the order link.
        Only show the required links; if all links are asked, then skip the order link, Only show the order link when asked explicitly, otherwise don't.

        FAQ Data:
        {json.dumps(faq_data, indent=2, ensure_ascii=False)}

        Standard Sculptures (images urls of the sculptures, use these when user asks for a sculpture image), [only utilize these urls and do create your own]:
        {json.dumps(sorted_matches, indent=2, ensure_ascii=False)}


        """
        conversation_text = "\n".join([f"User: {entry['user']}\nAI: {entry['ai']}" for entry in conversation_history])
        full_prompt = f"{custom_prompt}\n{conversation_text}\nUser: {user_input}\nAI:"


        # If there's an uploaded file (image)
        if uploaded_file:
            image_path = "uploaded_image.jpg"
            uploaded_file.save(image_path)
            
            instruction_text = """
            Describe the geometrical features of this image for an ice Sculpture.
            The ice should have a natural texture with light refraction.
            """

            base64_image = encode_image(image_path)
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }]
            )

            gpt_response = completion.choices[0].message.content
            if "https://theicebutcher.com/request/" in gpt_response:
                return jsonify({"image_url": "img.PNG"}) 



        # If the user input contains "generate", pass the prompt to DALL·E

        
        # Handle other chatbot input
        else:
            prompt_with_custom = f"{full_prompt}\n{user_input}"
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_with_custom}]
            )
            gpt_response = completion.choices[0].message.content
            conversation_history.append({"user": user_input, "ai": gpt_response})
            return jsonify({"response": gpt_response})
        


    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


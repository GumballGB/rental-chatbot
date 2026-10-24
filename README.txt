-*-*-*- RENTAL CHATBOT -*-*-*-

The Python Version of my computer is Python 3.12.7

Like all Python projects, this project requires its own virtual environment.
To activate the environment, do the following command:

--- FIRST SETUP ---
To setup this project for first-time users, you need to run the following commands;

1. Create the venv (virtual environment), the command is:

python3.12 -m venv .venv

If on LINUX, install the python venv w/ this line (it works on my computer)
sudo apt install python3-venv python3-pip

Then

python3 -m venv .venv

2. Activate the virtual environment with:

source .venv/bin/activate

3. Install the dependencies, it is found in a requirements.txt.

pip install -r requirements.txt
pip install -r requirements-dev.txt

4. Set up the key
This project uses Anthropic, copy the '.env.example' code and paste it into a new file called '.env'
You need to fill the Anthropic key placeholder 

To deactivate the venv, just type 'deactivate'

-**-**- TESTING -**-**-

To run testing, make sure you pip install the requirements-dev.txt file

python -m pytest





def choose_language():
    print("Please choose a language:\n")
    print("1. English")
    print("2. Francais")
    print("3. Dansk")
    print("4. Exit\n")
    choice = input("Enter the number of your choice: ")
    return choice

def display_english_header():
    print("Welcome to the Chatbot!")
    print("This chatbot will assist you in achieving your goals.")
    return 0

def display_french_header():
    print("Bienvenue au Chatbot!")
    print("Ce chatbot vous aidera à atteindre vos objectifs.")
    return 0

def display_danish_header():
    print("Velkommen til Chatbot!")
    print("Denne chatbot vil hjælpe dig med at nå dine mål.")
    return 0

def display_header():
    choice = choose_language()
    if choice == "1":
        display_english_header()
    elif choice == "2":
        display_french_header()
    elif choice == "3":
        display_danish_header()
    elif choice == "4":
        print("Exiting the program.")
        exit()
    else:
        print("Invalid choice. Please try again.")
        display_header()


if __name__ == "__main__":
    display_header()
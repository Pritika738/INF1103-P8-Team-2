"""
main.py

Entry point of the application. Coordinates the manager modules via a
simple CLI menu loop. Contains no business logic itself - it only
routes user choices to the appropriate modules.
"""

import io_manager
import data_manager


def handle_add_health_record():
    """Collect a new health record from the user and persist it."""
    record = io_manager.prompt_new_health_record()
    success = data_manager.add_health_record(record)
    if success:
        io_manager.show_message("Health record saved.")
    else:
        io_manager.show_message("Failed to save health record.")


def handle_view_health_history():
    """Load and display all stored health records."""
    records = data_manager.load_health_records()
    io_manager.show_health_records(records)


def run():
    """Main CLI loop: show the menu and dispatch the user's choice."""
    while True:
        io_manager.show_main_menu()
        choice = io_manager.get_menu_choice()

        if choice == "1":
            handle_add_health_record()
        elif choice == "2":
            handle_view_health_history()
        elif choice == "3":
            io_manager.show_placeholder("Analyse Health Records")
        elif choice == "4":
            io_manager.show_placeholder("Generate Consultation Report")
        elif choice == "5":
            io_manager.show_message("Goodbye!")
            break
        else:
            io_manager.show_message("Invalid option, please choose 1-5.")


if __name__ == "__main__":
    run()

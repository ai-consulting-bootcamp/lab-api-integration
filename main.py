
"""Interactive Multi-Provider News Summarizer application."""

from summarizer import NewsSummarizer


def display_menu():
    """Display available news categories."""
    print("\n" + "=" * 60)
    print("MULTI-PROVIDER NEWS SUMMARIZER")
    print("=" * 60)

    categories = {
        "1": "technology",
        "2": "business",
        "3": "science",
        "4": "health",
        "5": "entertainment",
        "6": "sports",
        "7": "general",
    }

    for number, category in categories.items():
        print(f"{number}. {category.capitalize()}")

    print("0. Exit")

    return categories


def get_category(categories):
    """Ask the user to select a valid news category."""
    while True:
        choice = input("\nSelect a category (0-7): ").strip()

        if choice == "0":
            return None

        if choice in categories:
            return categories[choice]

        print("Invalid choice. Please enter a number from 0 to 7.")


def get_article_count():
    """Ask how many articles to process."""
    while True:
        value = input("How many articles? (1-5): ").strip()

        try:
            count = int(value)

            if 1 <= count <= 5:
                return count

            print("Please choose between 1 and 5 articles.")

        except ValueError:
            print("Please enter a valid number.")


def main():
    """Run the interactive news summarizer."""
    try:
        summarizer = NewsSummarizer()

    except (ValueError, RuntimeError) as error:
        print(f"Configuration error: {error}")
        return

    while True:
        categories = display_menu()
        category = get_category(categories)

        if category is None:
            print("\nGoodbye!")
            break

        article_count = get_article_count()

        print(
            f"\nFetching {article_count} "
            f"{category} news articles..."
        )

        try:
            results = summarizer.process_news(
                category=category,
                country="us",
                limit=article_count,
            )

            if results:
                summarizer.print_results(results)
            else:
                print("\nNo articles were successfully processed.")

        except RuntimeError as error:
            print(f"\nProcessing stopped: {error}")

        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            break

        except Exception as error:
            print(
                f"\nUnexpected error: "
                f"{type(error).__name__}: {error}"
            )

        again = input(
            "\nWould you like to process more news? (y/n): "
        ).strip().lower()

        if again != "y":
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nApplication closed.")

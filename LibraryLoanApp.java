import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Community Library — book lending.
 *
 * SCOPE NOTE FOR ANALYSIS
 * -----------------------
 * This application deliberately contains exactly two modules:
 *
 *   1. FUNCTIONAL MODULE  — "Book Lending"
 *        The single business domain: lending copies to members, taking them
 *        back, and charging a fee when one is returned late.
 *
 *   2. TECHNICAL MODULE   — "Data Access Layer"
 *        The only infrastructure concern: in-memory storage of books and
 *        loans. It knows nothing about lending rules.
 *
 * There is no user management, no reporting, no billing, no configuration and
 * no logging concern. main() is a short driver, not an application layer.
 */
public class LibraryLoanApp {

    // ─────────────────────────────────────────────────────────────────────
    // FUNCTIONAL MODULE — Book Lending
    // ─────────────────────────────────────────────────────────────────────

    /** A book the library owns. */
    static class Book {
        final String isbn;
        final String title;
        boolean onLoan;

        Book(String isbn, String title) {
            this.isbn = isbn;
            this.title = title;
            this.onLoan = false;
        }
    }

    /** One book, lent to one member, due back on one date. */
    static class Loan {
        final String isbn;
        final String memberName;
        final LocalDate dueOn;

        Loan(String isbn, String memberName, LocalDate dueOn) {
            this.isbn = isbn;
            this.memberName = memberName;
            this.dueOn = dueOn;
        }
    }

    /** The lending rules: how long a loan lasts and what a late return costs. */
    static class LendingService {

        private static final int LOAN_DAYS = 14;
        private static final double LATE_FEE_PER_DAY = 0.25;

        private final LibraryRepository repository;

        LendingService(LibraryRepository repository) {
            this.repository = repository;
        }

        /** Lend a book to a member. Returns the due date. */
        LocalDate borrow(String isbn, String memberName, LocalDate today) {
            Book book = repository.findBook(isbn)
                    .orElseThrow(() -> new IllegalArgumentException("No such book: " + isbn));
            if (book.onLoan) {
                throw new IllegalStateException("Already on loan: " + book.title);
            }

            LocalDate dueOn = today.plusDays(LOAN_DAYS);
            book.onLoan = true;
            repository.saveLoan(new Loan(isbn, memberName, dueOn));
            return dueOn;
        }

        /** Take a book back. Returns the late fee, which is 0.00 when on time. */
        double returnBook(String isbn, LocalDate today) {
            Loan loan = repository.findOpenLoan(isbn)
                    .orElseThrow(() -> new IllegalStateException("Not on loan: " + isbn));

            long daysLate = today.toEpochDay() - loan.dueOn.toEpochDay();
            double fee = daysLate > 0 ? daysLate * LATE_FEE_PER_DAY : 0.0;

            repository.findBook(isbn).ifPresent(book -> book.onLoan = false);
            repository.closeLoan(isbn);
            return fee;
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // TECHNICAL MODULE — Data Access Layer
    // ─────────────────────────────────────────────────────────────────────

    /**
     * Stores books and loans in memory.
     *
     * Holds no lending rules: it can save and find records, and that is all.
     * Replacing it with a database would not change the module above.
     */
    static class LibraryRepository {

        private final List<Book> books = new ArrayList<>();
        private final List<Loan> openLoans = new ArrayList<>();

        void addBook(Book book) {
            books.add(book);
        }

        Optional<Book> findBook(String isbn) {
            return books.stream().filter(b -> b.isbn.equals(isbn)).findFirst();
        }

        void saveLoan(Loan loan) {
            openLoans.add(loan);
        }

        Optional<Loan> findOpenLoan(String isbn) {
            return openLoans.stream().filter(l -> l.isbn.equals(isbn)).findFirst();
        }

        void closeLoan(String isbn) {
            openLoans.removeIf(l -> l.isbn.equals(isbn));
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // Driver
    // ─────────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        LibraryRepository repository = new LibraryRepository();
        repository.addBook(new Book("978-0134685991", "Effective Java"));

        LendingService lending = new LendingService(repository);
        LocalDate borrowedOn = LocalDate.of(2026, 1, 5);

        LocalDate dueOn = lending.borrow("978-0134685991", "A. Member", borrowedOn);
        System.out.println("Due back on " + dueOn);

        double fee = lending.returnBook("978-0134685991", dueOn.plusDays(3));
        System.out.printf("Late fee: %.2f%n", fee);
    }
}

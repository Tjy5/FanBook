package com.fanbook.book.application;

import com.fanbook.auth.application.CurrentUser;
import com.fanbook.auth.application.CurrentUserProvider;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import java.util.List;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class BookAccessService {

    private final BookRepository bookRepository;
    private final CurrentUserProvider currentUserProvider;

    public BookAccessService(BookRepository bookRepository, CurrentUserProvider currentUserProvider) {
        this.bookRepository = bookRepository;
        this.currentUserProvider = currentUserProvider;
    }

    public BookEntity requireAccessibleBook(Long bookId) {
        BookEntity book = bookRepository.findById(bookId)
                .orElseThrow(() -> notFound(bookId));
        requireAccess(book);
        return book;
    }

    public void requireAccess(BookEntity book) {
        CurrentUser currentUser = currentUserProvider.requireCurrentUser();
        if (currentUser.hasRole(UserRole.ADMIN)) {
            return;
        }
        Long ownerUserId = book.getOwnerUserId();
        if (currentUser.id() != null && currentUser.id().equals(ownerUserId)) {
            return;
        }
        throw new FanbookException(
                ErrorCode.FORBIDDEN,
                HttpStatus.FORBIDDEN,
                "You do not have access to book '" + book.getId() + "'."
        );
    }

    public void requireAccessToSegment(SegmentEntity segment) {
        requireAccess(segment.getBook());
    }

    public List<BookEntity> listAccessibleBooks() {
        CurrentUser currentUser = currentUserProvider.requireCurrentUser();
        if (currentUser.hasRole(UserRole.ADMIN)) {
            return bookRepository.findAll(Sort.by(Sort.Direction.DESC, "id"));
        }
        if (currentUser.id() == null) {
            return List.of();
        }
        return bookRepository.findByOwnerUserIdOrderByIdDesc(currentUser.id());
    }

    private FanbookException notFound(Long bookId) {
        return new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found.");
    }
}

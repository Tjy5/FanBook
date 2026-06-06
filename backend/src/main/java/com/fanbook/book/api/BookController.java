package com.fanbook.book.api;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import java.io.IOException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
public class BookController {

    private final BookApplicationService bookApplicationService;

    public BookController(BookApplicationService bookApplicationService) {
        this.bookApplicationService = bookApplicationService;
    }

    @PostMapping("/api/books")
    @ResponseStatus(HttpStatus.CREATED)
    public BookResponse uploadBook(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "sourceLanguage", defaultValue = "en") String sourceLanguage,
            @RequestParam(value = "title", required = false) String title
    ) throws IOException {
        validateUpload(file);
        return bookApplicationService.uploadForCurrentUser(file.getOriginalFilename(), file.getBytes(), sourceLanguage, title);
    }

    @GetMapping("/api/books")
    public BookListResponse listBooks() {
        return bookApplicationService.listBooks();
    }

    @GetMapping("/api/books/{bookId}")
    public BookDetailResponse getBook(@PathVariable Long bookId) {
        return bookApplicationService.getBook(bookId);
    }

    @PatchMapping("/api/books/{bookId}/translated-title")
    public BookDetailResponse updateTranslatedTitle(
            @PathVariable Long bookId,
            @RequestBody TranslatedTitleRequest request
    ) {
        return bookApplicationService.updateTranslatedTitle(bookId, request.translatedTitle());
    }

    private static void validateUpload(MultipartFile file) {
        String filename = file.getOriginalFilename();
        if (filename == null || !filename.toLowerCase().endsWith(".epub")) {
            throw new FanbookException(ErrorCode.INVALID_EPUB, HttpStatus.BAD_REQUEST, "Uploaded file must use the .epub extension.");
        }
        String contentType = file.getContentType();
        if (contentType != null && !contentType.isBlank() && !"application/epub+zip".equals(contentType) && !"application/octet-stream".equals(contentType)) {
            throw new FanbookException(ErrorCode.INVALID_EPUB, HttpStatus.BAD_REQUEST, "Uploaded file must be an EPUB archive.");
        }
    }
}

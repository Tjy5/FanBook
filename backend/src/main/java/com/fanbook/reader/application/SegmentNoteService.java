package com.fanbook.reader.application;

import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.reader.api.CreateNoteRequest;
import com.fanbook.reader.api.SegmentNoteResponse;
import com.fanbook.reader.api.UpdateNoteRequest;
import com.fanbook.reader.domain.SegmentNoteEntity;
import com.fanbook.reader.infrastructure.SegmentNoteRepository;
import java.time.LocalDate;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SegmentNoteService {

    private final BookRepository bookRepository;
    private final SegmentRepository segmentRepository;
    private final SegmentNoteRepository noteRepository;

    public SegmentNoteService(
            BookRepository bookRepository,
            SegmentRepository segmentRepository,
            SegmentNoteRepository noteRepository
    ) {
        this.bookRepository = bookRepository;
        this.segmentRepository = segmentRepository;
        this.noteRepository = noteRepository;
    }

    @Transactional
    public SegmentNoteResponse create(Long segmentId, CreateNoteRequest request) {
        SegmentEntity segment = requireSegment(segmentId);
        SegmentNoteEntity note = noteRepository.save(new SegmentNoteEntity(
                segment.getBook(),
                segment,
                value(request == null ? null : request.content()),
                clean(request == null ? null : request.highlightColor()),
                "local"
        ));
        return toResponse(note);
    }

    @Transactional(readOnly = true)
    public List<SegmentNoteResponse> notes(Long segmentId) {
        requireSegment(segmentId);
        return noteRepository.findBySegmentIdOrderByCreatedAtAscIdAsc(segmentId).stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public SegmentNoteResponse update(Long noteId, UpdateNoteRequest request) {
        SegmentNoteEntity note = requireNote(noteId);
        note.update(
                value(request == null ? null : request.content()),
                clean(request == null ? null : request.highlightColor())
        );
        return toResponse(note);
    }

    @Transactional
    public void delete(Long noteId) {
        noteRepository.delete(requireNote(noteId));
    }

    @Transactional(readOnly = true)
    public String exportMarkdown(Long bookId) {
        BookEntity book = requireBook(bookId);
        StringBuilder markdown = new StringBuilder("# My Notes - ")
                .append(book.getTitle())
                .append("\n\n");
        String previousChapter = null;
        for (SegmentNoteEntity note : noteRepository.findByBookIdForExport(bookId)) {
            SegmentEntity segment = note.getSegment();
            String chapterTitle = segment.getChapter().getTitle();
            if (!chapterTitle.equals(previousChapter)) {
                markdown.append("## ").append(chapterTitle).append("\n\n");
                previousChapter = chapterTitle;
            }
            LocalDate createdDate = note.getCreatedAt() == null ? LocalDate.now() : note.getCreatedAt().toLocalDate();
            markdown.append("**Segment ").append(segment.getSegmentOrder()).append("** (").append(createdDate).append(")\n");
            markdown.append("> ").append(segment.getSourceText()).append("\n");
            if (segment.getTranslatedText() != null) {
                markdown.append("> ").append(segment.getTranslatedText()).append("\n");
            }
            markdown.append("\n**Note:** ").append(note.getNoteContent()).append("\n\n");
        }
        return markdown.toString();
    }

    private SegmentNoteResponse toResponse(SegmentNoteEntity note) {
        return new SegmentNoteResponse(
                note.getId(),
                note.getBook().getId(),
                note.getSegment().getId(),
                note.getNoteContent(),
                note.getHighlightColor(),
                note.getCreatedBy(),
                note.getCreatedAt(),
                note.getUpdatedAt()
        );
    }

    private BookEntity requireBook(Long bookId) {
        return bookRepository.findById(bookId)
                .orElseThrow(() -> new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found."));
    }

    private SegmentEntity requireSegment(Long segmentId) {
        return segmentRepository.findById(segmentId)
                .orElseThrow(() -> new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.NOT_FOUND, "Segment '" + segmentId + "' was not found."));
    }

    private SegmentNoteEntity requireNote(Long noteId) {
        return noteRepository.findById(noteId)
                .orElseThrow(() -> new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.NOT_FOUND, "Note '" + noteId + "' was not found."));
    }

    private String value(String candidate) {
        return candidate == null ? "" : candidate;
    }

    private String clean(String candidate) {
        return candidate == null || candidate.isBlank() ? null : candidate.trim();
    }
}

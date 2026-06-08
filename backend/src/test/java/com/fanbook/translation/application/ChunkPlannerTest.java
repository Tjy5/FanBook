package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.BookStatus;
import com.fanbook.book.domain.ChapterEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.domain.SegmentType;
import java.util.List;
import org.junit.jupiter.api.Test;

class ChunkPlannerTest {

    @Test
    void plansChunksWithoutCrossingChapterInputOrder() {
        ChunkPlanner planner = new ChunkPlanner(20, 2);
        BookEntity book = new BookEntity("demo.epub", "Demo", "en", "books/1/source.epub", BookStatus.PARSED);
        ChapterEntity chapter = new ChapterEntity(book, 1, "Chapter", "chapter.xhtml");
        SegmentEntity first = segment(book, chapter, 1, "short", "a");
        SegmentEntity second = segment(book, chapter, 2, "another short", "b");
        SegmentEntity third = segment(book, chapter, 3, "third", "c");

        List<List<SegmentEntity>> chunks = planner.plan(List.of(first, second, third));

        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0)).containsExactly(first, second);
        assertThat(chunks.get(1)).containsExactly(third);
    }

    @Test
    void startsNewChunkWhenChapterChanges() {
        ChunkPlanner planner = new ChunkPlanner(1000, 10);
        BookEntity book = new BookEntity("demo.epub", "Demo", "en", "books/1/source.epub", BookStatus.PARSED);
        ChapterEntity firstChapter = new ChapterEntity(book, 1, "Chapter 1", "chapter1.xhtml");
        ChapterEntity secondChapter = new ChapterEntity(book, 2, "Chapter 2", "chapter2.xhtml");
        SegmentEntity first = segment(book, firstChapter, 1, "first chapter text", "a");
        SegmentEntity second = segment(book, secondChapter, 1, "second chapter text", "b");

        List<List<SegmentEntity>> chunks = planner.plan(List.of(first, second));

        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0)).containsExactly(first);
        assertThat(chunks.get(1)).containsExactly(second);
    }

    @Test
    void keepsTitleWithFollowingParagraphWhenPossible() {
        ChunkPlanner planner = new ChunkPlanner(1000, 5);
        BookEntity book = new BookEntity("demo.epub", "Demo", "en", "books/1/source.epub", BookStatus.PARSED);
        ChapterEntity chapter = new ChapterEntity(book, 1, "Chapter", "chapter.xhtml");
        SegmentEntity title = segment(book, chapter, 1, "A New Room", SegmentType.TITLE, "a");
        SegmentEntity paragraph = segment(book, chapter, 2, "The room was quiet.", SegmentType.PARAGRAPH, "b");
        SegmentEntity nextTitle = segment(book, chapter, 3, "Another Room", SegmentType.TITLE, "c");

        List<List<SegmentEntity>> chunks = planner.plan(List.of(title, paragraph, nextTitle));

        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0)).containsExactly(title, paragraph);
        assertThat(chunks.get(1)).containsExactly(nextTitle);
    }

    @Test
    void keepsListItemsTogetherWithinBudget() {
        ChunkPlanner planner = new ChunkPlanner(1000, 5);
        BookEntity book = new BookEntity("demo.epub", "Demo", "en", "books/1/source.epub", BookStatus.PARSED);
        ChapterEntity chapter = new ChapterEntity(book, 1, "Chapter", "chapter.xhtml");
        SegmentEntity intro = segment(book, chapter, 1, "Inventory:", SegmentType.PARAGRAPH, "a");
        SegmentEntity first = segment(book, chapter, 2, "Red key", SegmentType.LIST_ITEM, "b");
        SegmentEntity second = segment(book, chapter, 3, "Blue map", SegmentType.LIST_ITEM, "c");
        SegmentEntity outro = segment(book, chapter, 4, "She packed them away.", SegmentType.PARAGRAPH, "d");

        List<List<SegmentEntity>> chunks = planner.plan(List.of(intro, first, second, outro));

        assertThat(chunks).hasSize(1);
        assertThat(chunks.getFirst()).containsExactly(intro, first, second, outro);
    }

    @Test
    void keepsDialogueRunTogetherWhenChunkMustBreak() {
        ChunkPlanner planner = new ChunkPlanner(60, 10);
        BookEntity book = new BookEntity("demo.epub", "Demo", "en", "books/1/source.epub", BookStatus.PARSED);
        ChapterEntity chapter = new ChapterEntity(book, 1, "Chapter", "chapter.xhtml");
        SegmentEntity narration = segment(book, chapter, 1, "The corridor stretched into shadow.", SegmentType.PARAGRAPH, "a");
        SegmentEntity firstLine = segment(book, chapter, 2, "\"Are you coming?\"", SegmentType.PARAGRAPH, "b");
        SegmentEntity secondLine = segment(book, chapter, 3, "\"In a minute.\"", SegmentType.PARAGRAPH, "c");
        SegmentEntity after = segment(book, chapter, 4, "The candle went out at once.", SegmentType.PARAGRAPH, "d");

        List<List<SegmentEntity>> chunks = planner.plan(List.of(narration, firstLine, secondLine, after));

        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0)).containsExactly(narration);
        assertThat(chunks.get(1)).containsExactly(firstLine, secondLine, after);
    }

    @Test
    void keepsQuoteAndPoetryRunsTogetherWithinBudget() {
        ChunkPlanner planner = new ChunkPlanner(1000, 10);
        BookEntity book = new BookEntity("demo.epub", "Demo", "en", "books/1/source.epub", BookStatus.PARSED);
        ChapterEntity chapter = new ChapterEntity(book, 1, "Chapter", "chapter.xhtml");
        SegmentEntity quoteOne = segment(book, chapter, 1, "First quoted line.", SegmentType.QUOTE, "a");
        SegmentEntity quoteTwo = segment(book, chapter, 2, "Second quoted line.", SegmentType.QUOTE, "b");
        SegmentEntity verseOne = segment(book, chapter, 3, "First verse.", SegmentType.POETRY, "c");
        SegmentEntity verseTwo = segment(book, chapter, 4, "Second verse.", SegmentType.POETRY, "d");

        List<List<SegmentEntity>> chunks = planner.plan(List.of(quoteOne, quoteTwo, verseOne, verseTwo));

        assertThat(chunks).hasSize(1);
        assertThat(chunks.getFirst()).containsExactly(quoteOne, quoteTwo, verseOne, verseTwo);
    }

    private static SegmentEntity segment(BookEntity book, ChapterEntity chapter, int order, String text, String digest) {
        return segment(book, chapter, order, text, SegmentType.PARAGRAPH, digest);
    }

    private static SegmentEntity segment(
            BookEntity book,
            ChapterEntity chapter,
            int order,
            String text,
            SegmentType type,
            String digest
    ) {
        return new SegmentEntity(book, chapter, order, text, type, SegmentStatus.PENDING, "{}", digest);
    }
}

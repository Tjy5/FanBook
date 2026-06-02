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

    private static SegmentEntity segment(BookEntity book, ChapterEntity chapter, int order, String text, String digest) {
        return new SegmentEntity(book, chapter, order, text, SegmentType.PARAGRAPH, SegmentStatus.PENDING, "{}", digest);
    }
}

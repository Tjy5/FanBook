package com.fanbook;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.BookStatus;
import com.fanbook.book.infrastructure.BookRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;

@DataJpaTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:fanbook;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class PersistenceSchemaTest {

    @Autowired
    BookRepository bookRepository;

    @Test
    void persistsBookWithSourceObjectKey() {
        BookEntity book = new BookEntity(
                "demo.epub",
                "Demo",
                "en",
                "books/1/source.epub",
                BookStatus.PARSED
        );

        BookEntity saved = bookRepository.saveAndFlush(book);

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getSourceObjectKey()).isEqualTo("books/1/source.epub");
        assertThat(saved.getStatus()).isEqualTo(BookStatus.PARSED);
    }
}

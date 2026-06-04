package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TranslationJobRepository extends JpaRepository<TranslationJobEntity, Long> {
    Optional<TranslationJobEntity> findFirstByBookIdOrderByUpdatedAtDescIdDesc(Long bookId);

    List<TranslationJobEntity> findByStatus(TranslationJobStatus status);
}

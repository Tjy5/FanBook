package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.ActiveTranslationSessionEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ActiveTranslationSessionRepository extends JpaRepository<ActiveTranslationSessionEntity, Long> {
    @Modifying(flushAutomatically = true)
    @Query(value = "INSERT INTO active_translation_sessions (book_id, job_id) VALUES (:bookId, :jobId)", nativeQuery = true)
    void insert(@Param("bookId") Long bookId, @Param("jobId") Long jobId);

    void deleteByJobId(Long jobId);
}

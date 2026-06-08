package com.fanbook.translation.infrastructure;

import com.fanbook.translation.domain.TranslationGlossaryCandidateEntity;
import com.fanbook.translation.domain.TranslationGlossaryCandidateStatus;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TranslationGlossaryCandidateRepository extends JpaRepository<TranslationGlossaryCandidateEntity, Long> {
    List<TranslationGlossaryCandidateEntity> findByBookIdAndStatusInOrderByIdAsc(
            Long bookId,
            Collection<TranslationGlossaryCandidateStatus> statuses
    );

    Optional<TranslationGlossaryCandidateEntity> findFirstByBookIdAndSourceNormOrderByIdAsc(Long bookId, String sourceNorm);
}

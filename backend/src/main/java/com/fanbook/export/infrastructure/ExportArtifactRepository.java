package com.fanbook.export.infrastructure;

import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.export.domain.ExportArtifactStatus;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExportArtifactRepository extends JpaRepository<ExportArtifactEntity, Long> {
    Optional<ExportArtifactEntity> findFirstByBook_IdAndKindOrderByCreatedAtDescIdDesc(Long bookId, ExportArtifactKind kind);

    Optional<ExportArtifactEntity> findFirstByBook_IdAndKindAndStatusOrderByCreatedAtDescIdDesc(Long bookId, ExportArtifactKind kind, ExportArtifactStatus status);
}

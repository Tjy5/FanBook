package com.fanbook.translation.application;

import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.translation.domain.TranslationCacheEntity;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.infrastructure.TranslationCacheRepository;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationCacheService {

    private final TranslationCacheRepository cacheRepository;

    public TranslationCacheService(TranslationCacheRepository cacheRepository) {
        this.cacheRepository = cacheRepository;
    }

    public String cacheKey(
            String sourceDigest,
            String sourceLanguage,
            String targetLanguage,
            String providerName,
            String modelName,
            String promptVersion
    ) {
        String raw = String.join("|", sourceDigest, sourceLanguage, targetLanguage, providerName, modelName, promptVersion);
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is not available.", exception);
        }
    }

    @Transactional
    public Optional<String> lookup(
            SegmentEntity segment,
            TranslationJobEntity job,
            String targetLanguage,
            String promptVersion
    ) {
        String key = cacheKey(
                segment.getSourceDigest(),
                segment.getBook().getSourceLanguage(),
                targetLanguage,
                job.getProviderName(),
                job.getModelName(),
                promptVersion
        );
        return cacheRepository.findByCacheKey(key)
                .map(cache -> {
                    cache.markUsed(OffsetDateTime.now());
                    cacheRepository.save(cache);
                    return cache.getTranslatedText();
                });
    }

    @Transactional
    public void store(
            SegmentEntity segment,
            TranslationJobEntity job,
            String targetLanguage,
            String promptVersion,
            String translatedText
    ) {
        String key = cacheKey(
                segment.getSourceDigest(),
                segment.getBook().getSourceLanguage(),
                targetLanguage,
                job.getProviderName(),
                job.getModelName(),
                promptVersion
        );
        if (cacheRepository.findByCacheKey(key).isPresent()) {
            return;
        }
        cacheRepository.save(new TranslationCacheEntity(
                key,
                segment.getSourceDigest(),
                segment.getBook().getSourceLanguage(),
                targetLanguage,
                job.getProviderName(),
                job.getModelName(),
                promptVersion,
                translatedText
        ));
    }
}

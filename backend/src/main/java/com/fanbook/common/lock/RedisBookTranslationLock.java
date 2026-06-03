package com.fanbook.common.lock;

import java.time.Duration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component
@Profile("!local")
public class RedisBookTranslationLock implements BookTranslationLock {

    private static final Duration LOCK_TTL = Duration.ofMinutes(30);

    private final StringRedisTemplate redisTemplate;

    public RedisBookTranslationLock(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    public boolean acquire(Long bookId, Long jobId) {
        Boolean result = redisTemplate.opsForValue().setIfAbsent(key(bookId), String.valueOf(jobId), LOCK_TTL);
        return Boolean.TRUE.equals(result);
    }

    @Override
    public void release(Long bookId, Long jobId) {
        String key = key(bookId);
        String value = redisTemplate.opsForValue().get(key);
        if (String.valueOf(jobId).equals(value)) {
            redisTemplate.delete(key);
        }
    }

    private static String key(Long bookId) {
        return "fanbook:book:" + bookId + ":translation-lock";
    }
}

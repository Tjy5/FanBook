package com.fanbook.common.lock;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component
@Profile("local")
public class InMemoryBookTranslationLock implements BookTranslationLock {

    private final ConcurrentMap<Long, Long> locks = new ConcurrentHashMap<>();

    @Override
    public boolean acquire(Long bookId, Long jobId) {
        return locks.putIfAbsent(bookId, jobId) == null;
    }

    @Override
    public void release(Long bookId, Long jobId) {
        locks.remove(bookId, jobId);
    }
}

package com.fanbook.common.lock;

public interface BookTranslationLock {
    boolean acquire(Long bookId, Long jobId);

    void release(Long bookId, Long jobId);
}

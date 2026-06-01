package com.fanbook;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.SpringBootApplication;

class FanbookApplicationTests {

    @Test
    void applicationClassIsSpringBootEntryPoint() {
        assertThat(FanbookApplication.class.isAnnotationPresent(SpringBootApplication.class)).isTrue();
    }
}

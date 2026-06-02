package com.fanbook;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class FanbookApplication {

    public static void main(String[] args) {
        SpringApplication.run(FanbookApplication.class, args);
    }
}

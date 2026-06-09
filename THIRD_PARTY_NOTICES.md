# Third-Party Notices

Fanbook is released under the MIT License. It depends on third-party open
source software with their own licenses. This file is a repository-level
summary for source distribution and is not a substitute for a full legal review
of packaged binaries, container images, or hosted deployments.

## Backend Runtime

The Java backend is built on Spring Boot and related Spring projects, which are
licensed under Apache License 2.0. It also uses common runtime libraries from
the Java ecosystem, including Jackson, Hibernate, Flyway, RabbitMQ Java client,
Netty, Tomcat, Logback, Micrometer, HikariCP, and springdoc-openapi.

Notable backend dependency licenses from the local Maven metadata:

| Dependency | License notes |
| --- | --- |
| Spring Boot and Spring Framework | Apache License 2.0 |
| MySQL Connector/J | GPLv2 with Universal FOSS Exception |
| H2 Database | MPL 2.0 or EPL 1.0 |
| Apache Tomcat embedded runtime | Apache License 2.0 |
| Netty | Apache License 2.0 |
| Logback | EPL 1.0 or LGPL 2.1 |
| Jackson | Apache License 2.0 |
| Hibernate ORM | LGPL 2.1 |

## Frontend Runtime and Tooling

The Vite React frontend depends on packages from npm. Licenses observed in the
local lockfile include MIT, Apache-2.0, ISC, BSD-3-Clause, 0BSD, and MPL-2.0.

Notable frontend dependency licenses from the local npm metadata:

| Dependency | License |
| --- | --- |
| React | MIT |
| React DOM | MIT |
| Vite | MIT |
| TypeScript | Apache-2.0 |
| @vitejs/plugin-react | MIT |
| Playwright | Apache-2.0 |
| lucide-react | ISC |
| lightningcss | MPL-2.0 |

## Distribution Notes

- Preserve upstream license texts and notices when redistributing compiled
  assets, dependency bundles, container images, or archives.
- Re-run dependency license checks before publishing binaries or images.
- Review license obligations again whenever adding new backend or frontend
  dependencies.

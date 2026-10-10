# Источники методики

Официальные документы и первичные источники изучены 2026-10-10. Ниже — краткие выводы, применённые в скилле. Это методы проверки, а не обещание конкретного результата.

- [Playwright: Visual comparisons](https://playwright.dev/docs/test-snapshots) — сравнение скриншотов и ограничения воспроизводимости rendering; baseline требует стабильного окружения.
- [Playwright: Accessibility testing](https://playwright.dev/docs/accessibility-testing) — автоматический axe-проход дополняется ручной проверкой; раскрытые состояния надо проверять отдельно.
- [W3C: Evaluating Web Accessibility](https://www.w3.org/WAI/test-evaluate/) — ни один инструмент сам не определяет полное соответствие; нужен человеческий анализ и обозначенный охват.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) — проверяемые критерии доступности. При формальном аудите сверять применимый уровень и конкретные критерии.
- [web.dev: Learn Testing](https://web.dev/learn/testing) — выбор методов и тестового покрытия для веб-приложений.
- [web.dev: Web Vitals](https://web.dev/articles/vitals) — LCP, INP, CLS, пороги и отличие полевого измерения от лабораторного.
- [Google Search: SEO guide for developers](https://developers.google.com/search/docs/fundamentals/get-started-developers) — проверка метаданных, доступности контента и публичных страниц; SEO не гарантирует ранжирование.
- [Jakob Nielsen: 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) — оценка ясности обратной связи, согласованности, предотвращения ошибок и восстановления. Эвристики помогают формулировать гипотезы; пользовательский тест даёт отдельные доказательства.

Решение Beoma: сочетать эти методы, выдавать прозрачное покрытие и автоматизировать цепочку «обнаружено → исправлено → перепроверено» с интерактивным отчётом. Это наш выбор процесса, а не предписание источников.

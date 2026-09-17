# Cross-platform delivery rule

Product-facing changes must be assessed and implemented across all supported clients by default:

- Web and desktop
- Android
- iOS
- HarmonyOS
- WeChat Mini Program

For every product change, also review the shared server contract, user isolation, client source headers, and regression coverage. A platform may be marked as no-change only when the behavior is already provided by the shared contract or is not applicable, and that decision must be stated in the delivery summary.

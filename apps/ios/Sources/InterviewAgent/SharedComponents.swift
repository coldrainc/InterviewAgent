import SwiftUI

struct MetricBox: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title2.weight(.bold))
                .foregroundStyle(BrandPalette.teal)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(BrandPalette.surfaceSoft)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

struct InfoRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .top) {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .multilineTextAlignment(.trailing)
        }
        .font(.subheadline)
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(message.text)
                .padding(12)
                .foregroundStyle(message.role == .user ? Color.white : BrandPalette.text)
                .background(message.role == .user ? BrandPalette.primary : Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
    }

    private var label: String {
        switch message.role {
        case .user:
            return "我"
        case .agent:
            return "面试官"
        case .system:
            return "系统"
        }
    }
}

extension View {
    func cardStyle() -> some View {
        padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

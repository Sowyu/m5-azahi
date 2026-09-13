import Foundation
import Compression

// Read-only IM4P input; generated analysis output only, never overwrite.
guard (3...4).contains(CommandLine.arguments.count) else { fatalError("input.im4p output [ibot|ibdt|sptm]") }
let payloadType = CommandLine.arguments.count == 4 ? CommandLine.arguments[3] : "krnl"
precondition(["krnl", "ibot", "ibdt", "sptm"].contains(payloadType))
let input = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
let output = CommandLine.arguments[2]
guard !FileManager.default.fileExists(atPath: output) else { fatalError("Output already exists") }
let bytes = [UInt8](input)
func tlv(_ offset: Int) -> (tag: UInt8, start: Int, end: Int) {
    precondition(offset >= 0 && offset + 2 <= bytes.count)
    let tag = bytes[offset]
    var cursor = offset + 2
    var length = Int(bytes[offset + 1])
    if length & 0x80 != 0 {
        let count = length & 0x7f
        precondition(count > 0 && count <= 4 && cursor + count <= bytes.count)
        length = 0
        for _ in 0..<count { length = length * 256 + Int(bytes[cursor]); cursor += 1 }
    }
    precondition(length <= bytes.count - cursor)
    return (tag, cursor, cursor + length)
}
let top = tlv(0)
precondition(top.tag == 0x30 && top.end == bytes.count)
var cursor = top.start
for expected in ["IM4P", payloadType] {
    let item = tlv(cursor)
    precondition(item.tag == 0x16 && String(bytes: bytes[item.start..<item.end], encoding: .ascii) == expected)
    cursor = item.end
}
let description = tlv(cursor)
precondition(description.tag == 0x16)
let payload = tlv(description.end)
precondition(payload.tag == 4 && payload.end <= top.end)
let compressed = input.subdata(in: payload.start..<payload.end)
precondition(compressed.prefix(4) == Data("bvx2".utf8))
var decoded = Data(count: 256 * 1024 * 1024)
let length = decoded.withUnsafeMutableBytes { destination in
    compressed.withUnsafeBytes { source in
        compression_decode_buffer(destination.bindMemory(to: UInt8.self).baseAddress!, destination.count,
                                  source.bindMemory(to: UInt8.self).baseAddress!, source.count,
                                  nil, COMPRESSION_LZFSE)
    }
}
precondition(length > 0 && length < decoded.count)
decoded.count = length
if payloadType == "krnl" {
    precondition(decoded.prefix(4) == Data([0xcf, 0xfa, 0xed, 0xfe]))
} else {
    precondition(length < 16 * 1024 * 1024)
}
try decoded.write(to: URL(fileURLWithPath: output), options: .withoutOverwriting)
print("IM4P_DECODED type=\(payloadType) \(length) bytes -> \(output)")

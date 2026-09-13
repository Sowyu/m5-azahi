// Read-only local OCR of an already captured target-screen photograph.
import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count == 2 else {
    fatalError("Usage: swift probe/read-screen.swift image.jpg")
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.minimumTextHeight = 0.003
let handler = VNImageRequestHandler(url: url, options: [:])
try handler.perform([request])
for observation in request.results ?? [] {
    if let candidate = observation.topCandidates(1).first {
        print(candidate.string)
    }
}

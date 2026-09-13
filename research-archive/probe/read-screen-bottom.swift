// Read-only OCR: crop/scale in memory for console diagnostics, no edited image.
import Foundation
import Vision
import CoreImage
guard CommandLine.arguments.count == 2,
      let source = CIImage(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    fatalError("Usage: swift probe/read-screen-bottom.swift photo.jpg")
}
let region = CGRect(x: 380, y: 370, width: 1160, height: 310)
let context = CIContext()
for contrast in [1.0, 1.6] {
    let candidate = source.cropped(to: region).transformed(by: CGAffineTransform(scaleX: 3, y: 3))
        .applyingFilter("CIColorControls", parameters: ["inputSaturation": 0.0, "inputContrast": contrast])
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.002
    guard let rendered = context.createCGImage(candidate, from: candidate.extent) else { continue }
    try VNImageRequestHandler(cgImage: rendered, options: [:]).perform([request])
    print("CONTRAST", contrast)
    for observation in request.results ?? [] {
        if let result = observation.topCandidates(1).first { print(result.string) }
    }
}

// Read local kernel crash QR codes; never open a decoded URL.
import Foundation
import Vision
import CoreImage

guard CommandLine.arguments.count == 2 else {
    fatalError("Usage: swift probe/read-panic-qr.swift photograph.jpg")
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
var found = false
func decode(_ handler: VNImageRequestHandler) throws {
    let request = VNDetectBarcodesRequest()
    request.symbologies = [.qr]
    try handler.perform([request])
    for observation in request.results ?? [] {
    if let text = observation.payloadStringValue {
        print("PANIC_QR_BEGIN")
        print(text)
        print("PANIC_QR_END")
        found = true
    }
    }
}
try decode(VNImageRequestHandler(url: url, options: [:]))
// Analysis-only perspective normalization of the known webcam framing.
// No modified image is written and decoded content is never opened.
if !found, let source = CIImage(contentsOf: url), source.extent.width == 1920 {
    let corrected = source.applyingFilter("CIPerspectiveCorrection", parameters: [
        "inputTopLeft": CIVector(x: 726, y: 924),
        "inputTopRight": CIVector(x: 1212, y: 928),
        "inputBottomLeft": CIVector(x: 746, y: 459),
        "inputBottomRight": CIVector(x: 1194, y: 459),
    ])
    for contrast in [1.0, 1.5, 2.0] {
        let candidate = corrected.applyingFilter("CIColorControls", parameters: [
            "inputSaturation": 0.0, "inputContrast": contrast,
        ])
        try decode(VNImageRequestHandler(ciImage: candidate, options: [:]))
        if found { break }
    }
}
if !found { print("NO_READABLE_QR") }

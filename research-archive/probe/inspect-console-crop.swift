// Analytical crop of a local diagnostic photograph; original is unchanged.
import Foundation
import CoreImage
import ImageIO
import UniformTypeIdentifiers
guard CommandLine.arguments.count == 3,
      let source = CIImage(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    fatalError("usage: inspect-console-crop.swift input.jpg new-crop.png")
}
let destination = URL(fileURLWithPath: CommandLine.arguments[2])
guard !FileManager.default.fileExists(atPath: destination.path) else { fatalError("Refuse overwrite") }
let crop = source.cropped(to: CGRect(x: 440, y: 230, width: 580, height: 340))
    .transformed(by: CGAffineTransform(scaleX: 3, y: 3))
let context = CIContext()
guard let cg = context.createCGImage(crop, from: crop.extent),
      let out = CGImageDestinationCreateWithURL(destination as CFURL, UTType.png.identifier as CFString, 1, nil) else {
    fatalError("Cannot create diagnostic crop")
}
CGImageDestinationAddImage(out, cg, nil)
guard CGImageDestinationFinalize(out) else { fatalError("Write failed") }

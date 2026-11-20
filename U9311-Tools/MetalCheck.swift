import Foundation
import Metal

func fail(_ message: String) -> Never {
    print(message)
    exit(1)
}

guard let gpu = MTLCreateSystemDefaultDevice(),
      let queue = gpu.makeCommandQueue() else {
    fail("No usable Metal device or command queue.")
}

let source = """
#include <metal_stdlib>
using namespace metal;
kernel void increment(device uint *value [[buffer(0)]]) { value[0] += 1u; }
"""
do {
    let library = try gpu.makeLibrary(source: source, options: nil)
    guard let kernel = library.makeFunction(name: "increment"),
          let data = gpu.makeBuffer(length: MemoryLayout<UInt32>.stride, options: .storageModeShared),
          let command = queue.makeCommandBuffer(),
          let encoder = command.makeComputeCommandEncoder() else {
        fail("Metal allocation failed.")
    }
    let pipeline = try gpu.makeComputePipelineState(function: kernel)
    let value = data.contents().bindMemory(to: UInt32.self, capacity: 1)
    value.pointee = 41
    encoder.setComputePipelineState(pipeline)
    encoder.setBuffer(data, offset: 0, index: 0)
    let one = MTLSize(width: 1, height: 1, depth: 1)
    encoder.dispatchThreadgroups(one, threadsPerThreadgroup: one)
    encoder.endEncoding()
    command.commit()
    command.waitUntilCompleted()
    guard command.status == .completed, value.pointee == 42 else {
        fail("GPU command failed: \(String(describing: command.error)) / result \(value.pointee)")
    }
    print("PASS: \(gpu.name) ran the Metal kernel. GPU result = 42.")
} catch {
    fail("Metal error: \(error)")
}

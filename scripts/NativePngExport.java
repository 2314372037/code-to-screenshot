import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Transfers the renderer's exact PNG bytes; no ImageIO decode, redraw or resampling. */
class NativePngExport {
    public static void main(String[] args) throws IOException {
        if (args.length != 1) throw new IllegalArgumentException("Expected one native PNG path");
        Path file = Path.of(args[0]);
        if (Files.size(file) > 128L * 1024 * 1024) throw new IOException("Native PNG exceeds 128 MiB");
        byte[] bytes = Files.readAllBytes(file);
        byte[] signature = {(byte) 137, 80, 78, 71, 13, 10, 26, 10};
        if (bytes.length < signature.length) throw new IOException("Incomplete native PNG");
        for (int i = 0; i < signature.length; i++) {
            if (bytes[i] != signature[i]) throw new IOException("Renderer output is not a PNG");
        }
        System.out.write(bytes);
        System.out.flush();
    }
}

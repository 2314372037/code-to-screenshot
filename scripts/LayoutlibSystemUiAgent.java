import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.*;

/** alpha16's standalone bootstrap disables decorations unconditionally.
 * Restore Layoutlib's native decorations only for our explicitly marked previews.
 * No pixels are painted here. No dependency or Gradle cache is modified.
 */
public final class LayoutlibSystemUiAgent {
    public static void premain(String args, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            public byte[] transform(ClassLoader loader, String name, Class<?> type,
                                    ProtectionDomain domain, byte[] bytes) {
                if (!name.equals("com/android/tools/render/Renderer")) return null;
                ClassReader reader = new ClassReader(bytes);
                ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                    public MethodVisitor visitMethod(int access, String name, String descriptor,
                                                     String signature, String[] exceptions) {
                        MethodVisitor delegate = super.visitMethod(access, name, descriptor, signature, exceptions);
                        if (!name.equals("render") || !descriptor.equals("(Lcom/android/tools/configurations/Configuration;Ljava/lang/String;)Lcom/android/tools/rendering/RenderResult;")) return delegate;
                        return new MethodVisitor(Opcodes.ASM8, delegate) {
                            public void visitCode() {
                                super.visitCode();
                                super.visitVarInsn(Opcodes.ALOAD, 1);
                                super.visitVarInsn(Opcodes.ALOAD, 2);
                                super.visitMethodInsn(Opcodes.INVOKESTATIC, "LayoutlibSystemUiAgent", "theme",
                                    "(Ljava/lang/Object;Ljava/lang/String;)V", false);
                            }
                            public void visitMethodInsn(int opcode, String owner, String name,
                                                        String descriptor, boolean isInterface) {
                                if (owner.equals("com/android/tools/rendering/RenderTask") && name.equals("render") && descriptor.equals("()Ljava/util/concurrent/CompletableFuture;")) {
                                    super.visitInsn(Opcodes.DUP);
                                    super.visitVarInsn(Opcodes.ALOAD, 2);
                                    super.visitMethodInsn(Opcodes.INVOKESTATIC, "LayoutlibSystemUiAgent", "configure",
                                        "(Ljava/lang/Object;Ljava/lang/String;)V", false);
                                }
                                super.visitMethodInsn(opcode, owner, name, descriptor, isInterface);
                            }
                        };
                    }
                }, 0);
                return writer.toByteArray();
            }
        });
    }

    public static void theme(Object configuration, String xml) {
        if (!xml.contains("dev.codetoscreenshot.generated.") || !xml.contains("__system_ui")) return;
        try {
            configuration.getClass().getMethod("setTheme", String.class).invoke(configuration,
                "@style/CodeToScreenshot" + (xml.contains("__system_ui_dark") ? "Dark" : "Light"));
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("Cannot configure native system UI theme", ex);
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    public static void configure(Object task, String xml) {
        if (!xml.contains("dev.codetoscreenshot.generated.") || !xml.contains("__system_ui")) return;
        try {
            task.getClass().getMethod("setDecorations", boolean.class).invoke(task, true);
            Class mode = Class.forName("com.android.ide.common.rendering.api.SessionParams$RenderingMode", true, task.getClass().getClassLoader());
            task.getClass().getMethod("setRenderingMode", mode).invoke(task, Enum.valueOf(mode, "NORMAL"));
            System.err.println("CODE_TO_SCREENSHOT_NATIVE_SYSTEM_UI " + xml);
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("Cannot enable native Layoutlib system UI", ex);
        }
    }
}

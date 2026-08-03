/// Dalvik access_flags bitfield to readable modifier string (Java-style).
pub fn access_flags_string(flags: u32) -> String {
    const ACC_PUBLIC: u32 = 0x0001;
    const ACC_PRIVATE: u32 = 0x0002;
    const ACC_PROTECTED: u32 = 0x0004;
    const ACC_STATIC: u32 = 0x0008;
    const ACC_FINAL: u32 = 0x0010;
    const ACC_SYNCHRONIZED: u32 = 0x0020;
    const ACC_BRIDGE: u32 = 0x0040;
    const ACC_VARARGS: u32 = 0x0080;
    const ACC_NATIVE: u32 = 0x0100;
    const ACC_INTERFACE: u32 = 0x0200;
    const ACC_ABSTRACT: u32 = 0x0400;
    const ACC_STRICT: u32 = 0x0800;
    const ACC_SYNTHETIC: u32 = 0x1000;
    const ACC_ANNOTATION: u32 = 0x2000;
    const ACC_ENUM: u32 = 0x4000;

    let mut parts: Vec<&str> = Vec::new();
    if flags & ACC_PUBLIC != 0 {
        parts.push("public");
    }
    if flags & ACC_PRIVATE != 0 {
        parts.push("private");
    }
    if flags & ACC_PROTECTED != 0 {
        parts.push("protected");
    }
    if flags & ACC_STATIC != 0 {
        parts.push("static");
    }
    if flags & ACC_FINAL != 0 {
        parts.push("final");
    }
    if flags & ACC_SYNCHRONIZED != 0 {
        parts.push("synchronized");
    }
    if flags & ACC_BRIDGE != 0 {
        parts.push("bridge");
    }
    if flags & ACC_VARARGS != 0 {
        parts.push("varargs");
    }
    if flags & ACC_NATIVE != 0 {
        parts.push("native");
    }
    if flags & ACC_INTERFACE != 0 {
        parts.push("interface");
    }
    if flags & ACC_ABSTRACT != 0 {
        parts.push("abstract");
    }
    if flags & ACC_STRICT != 0 {
        parts.push("strictfp");
    }
    if flags & ACC_SYNTHETIC != 0 {
        parts.push("synthetic");
    }
    if flags & ACC_ANNOTATION != 0 {
        parts.push("annotation");
    }
    if flags & ACC_ENUM != 0 {
        parts.push("enum");
    }
    parts.join(" ")
}

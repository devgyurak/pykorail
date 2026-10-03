import android.util.Base64;
import java.nio.charset.StandardCharsets;
import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

public class PasswordVectors {
    public static void main(String[] args) throws Exception {
        String key = "0123456789abcdef0123456789abcdef";
        String[] passwords = {"", "a", "a".repeat(15), "a".repeat(16), "a".repeat(31),
                              "a".repeat(32), "a".repeat(64), "한글🙂".repeat(3), "한글🙂".repeat(4)};
        System.out.println("[");
        for (int i = 0; i < passwords.length; i++) {
            Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
            cipher.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "AES"),
                        new IvParameterSpec(key.substring(0,16).getBytes(StandardCharsets.UTF_8)));
            String inner = Base64.encodeToString(cipher.doFinal(passwords[i].getBytes(StandardCharsets.UTF_8)), 2);
            String outer = Base64.encodeToString(inner.getBytes(StandardCharsets.UTF_8), 8);
            System.out.print("{\"password\":\"" + passwords[i] + "\",\"key\":\"" + key +
                "\",\"expected\":\"" + outer.replace("\n", "\\n") + "\"}");
            System.out.println(i == passwords.length - 1 ? "" : ",");
        }
        System.out.println("]");
    }
}

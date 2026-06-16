import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.ComponentDrawContext;
import com.cburch.logisim.data.Bounds;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.prefs.AppPreferences;
import com.cburch.logisim.proj.Project;

/**
 * Headless renderer: load a {@code .circ} and paint its {@code main} circuit to
 * a PNG using Logisim-evolution's own drawing code, so the figure looks exactly
 * like the GUI (crisp black wires, junction dots, opaque shaped gate bodies).
 *
 * <p>Usage: {@code java -Djava.awt.headless=true -cp ".:$LOGISIM_JAR" LogiRender in.circ out.png [scale]}
 *
 * <p>Render the {@code *_fig.circ} (label) variant for clean figures: it has
 * Text labels instead of input/output Pins, so nothing renders as an unknown
 * ("x") value.
 */
public class LogiRender {
  public static void main(String[] args) throws Exception {
    if (args.length < 2) {
      System.err.println("usage: LogiRender in.circ out.png [scale]");
      System.exit(2);
    }
    String in = args[0], out = args[1];
    double scale = 4.0;
    if (args.length > 2) {
      try {
        scale = Double.parseDouble(args[2]);
      } catch (NumberFormatException e) {
        System.err.println("error: scale must be a number, got: " + args[2]);
        System.exit(2);
      }
    }
    int margin = 16;

    File inFile = new File(in);
    if (!inFile.isFile()) {
      System.err.println("error: input circuit not found: " + in);
      System.exit(2);
    }

    AppPreferences.GATE_SHAPE.set(AppPreferences.SHAPE_SHAPED);

    Loader loader = new Loader(null);
    LogisimFile lf;
    try {
      lf = loader.openLogisimFile(inFile);
    } catch (Exception e) {
      System.err.println("error: could not open '" + in + "' as a Logisim .circ: "
          + e.getMessage());
      System.exit(1);
      return;
    }
    Project proj = new Project(lf);
    Circuit circ = lf.getCircuit("main");
    if (circ == null) circ = lf.getCircuits().get(0);
    CircuitState state = CircuitState.createRootState(proj, circ);

    // measure the circuit's bounding box
    BufferedImage probe = new BufferedImage(1, 1, BufferedImage.TYPE_INT_ARGB);
    Graphics2D pg = probe.createGraphics();
    Bounds b = circ.getBounds(pg);
    pg.dispose();

    int w = (int) Math.ceil((b.getWidth() + 2 * margin) * scale);
    int h = (int) Math.ceil((b.getHeight() + 2 * margin) * scale);

    BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
    Graphics2D g = img.createGraphics();
    g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
    g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
    g.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE);
    g.setColor(Color.WHITE);
    g.fillRect(0, 0, w, h);
    g.scale(scale, scale);
    g.translate(margin - b.getX(), margin - b.getY());

    ComponentDrawContext ctx =
        new ComponentDrawContext(null, circ, state, g, g, true); // printView=true
    ctx.setShowColor(false);
    // Let Logisim paint the whole circuit (correct z-order: black wires with
    // junction dots, then opaque gate bodies). This is the crisp standard look;
    // do NOT replace it with per-wire draws + white-out rectangles (that yields
    // gray wires and erases junction dots).
    circ.draw(ctx, java.util.Collections.emptySet());

    g.dispose();
    ImageIO.write(img, "PNG", new File(out));
    System.out.println("wrote " + out + " (" + w + "x" + h + ")");

    // ImageIO leaves a non-daemon AWT thread alive, which keeps the JVM running
    // forever; without this exit, batch rendering piles up hung JVMs that
    // exhaust memory. Exit explicitly.
    System.exit(0);
  }
}

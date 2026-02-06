use cocoa::appkit::{
    NSApp, NSApplication, NSApplicationActivationPolicy, NSBackingStoreType, NSColor,
    NSView, NSWindow, NSWindowCollectionBehavior, NSWindowStyleMask,
};
use cocoa::base::{id, nil, NO, YES};
use cocoa::foundation::{NSAutoreleasePool, NSPoint, NSRect, NSSize};
use core_graphics::context::CGContext;
use core_graphics::geometry::{CGPoint, CGRect, CGSize};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use objc::declare::ClassDecl;
use objc::runtime::{Object, Sel};
use objc::{class, msg_send, sel, sel_impl};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::thread;
use std::time::Duration;

// Carbon API for TransformProcessType
#[link(name = "Carbon", kind = "framework")]
extern "C" {
    fn TransformProcessType(psn: *const ProcessSerialNumber, transformState: u32) -> i32;
}

#[repr(C)]
struct ProcessSerialNumber {
    high_long_of_psn: u32,
    low_long_of_psn: u32,
}

const K_CURRENT_PROCESS: ProcessSerialNumber = ProcessSerialNumber {
    high_long_of_psn: 0,
    low_long_of_psn: 2, // kCurrentProcess
};
const K_PROCESS_TRANSFORM_TO_FOREGROUND_APPLICATION: u32 = 1;

const WINDOW_WIDTH: f64 = 120.0;
const WINDOW_HEIGHT: f64 = 40.0;
const PADDING: f64 = 6.0;
const CORNER_RADIUS: f64 = 8.0;

// Shared state for audio level (using atomic for thread safety)
static AUDIO_LEVEL_BITS: AtomicU64 = AtomicU64::new(0);
static RUNNING: AtomicBool = AtomicBool::new(true);

fn set_audio_level(level: f32) {
    AUDIO_LEVEL_BITS.store(level.to_bits() as u64, Ordering::Relaxed);
}

fn get_audio_level() -> f32 {
    f32::from_bits(AUDIO_LEVEL_BITS.load(Ordering::Relaxed) as u32)
}

fn main() {
    // Transform to foreground app - required for subprocess to show windows from Raycast
    unsafe {
        TransformProcessType(&K_CURRENT_PROCESS, K_PROCESS_TRANSFORM_TO_FOREGROUND_APPLICATION);
    }

    unsafe {
        // Keep pool alive for entire app lifetime
        let _pool = NSAutoreleasePool::new(nil);

        // Initialize the application
        let app = NSApp();
        app.setActivationPolicy_(NSApplicationActivationPolicy::NSApplicationActivationPolicyAccessory);

        // Finish launching - required for subprocess GUI
        let _: () = msg_send![app, finishLaunching];

        // Register custom view class
        register_level_view_class();

        // Create the floating panel
        let panel = create_floating_panel();

        // Retain panel to prevent deallocation
        let _: () = msg_send![panel, retain];

        // Create and set the custom view
        let view = create_level_view();
        panel.setContentView_(view);

        // Position the panel
        position_panel(panel);

        // Activate the app for subprocess windows
        let _: () = msg_send![app, activateIgnoringOtherApps: YES];

        // Show the window - use orderFrontRegardless for subprocess
        let _: () = msg_send![panel, orderFrontRegardless];
        let _: () = msg_send![panel, makeKeyAndOrderFront: nil];

        // Start audio capture thread
        thread::spawn(move || {
            capture_audio();
        });

        // Listen for STOP signal via file (more reliable than stdin from Raycast)
        thread::spawn(move || {
            let stop_file = std::path::Path::new("/tmp/gglisten-level-meter-stop");

            // Clean up any stale stop file
            let _ = std::fs::remove_file(stop_file);

            loop {
                // Check for stop file
                if stop_file.exists() {
                    let _ = std::fs::remove_file(stop_file);
                    RUNNING.store(false, Ordering::SeqCst);
                    dispatch_terminate();
                    break;
                }

                thread::sleep(Duration::from_millis(50));

                // Also check RUNNING flag (in case it's set elsewhere)
                if !RUNNING.load(Ordering::SeqCst) {
                    dispatch_terminate();
                    break;
                }
            }
        });

        // Set up a timer for redrawing
        let _timer: id = msg_send![class!(NSTimer),
            scheduledTimerWithTimeInterval: 0.033f64
            target: view
            selector: sel!(refresh:)
            userInfo: nil
            repeats: YES
        ];

        // Run the application
        app.run();

        // Cleanup: release panel (after app.run() returns)
        let _: () = msg_send![panel, release];
    }
}

fn dispatch_terminate() {
    // Give the audio thread time to pause the stream before exiting
    thread::sleep(Duration::from_millis(200));
    std::process::exit(0);
}

#[allow(deprecated)]
unsafe fn create_floating_panel() -> id {
    let frame = NSRect::new(NSPoint::new(0.0, 0.0), NSSize::new(WINDOW_WIDTH, WINDOW_HEIGHT));

    // Use borderless style
    let style = NSWindowStyleMask::NSBorderlessWindowMask;

    let panel: id = msg_send![class!(NSPanel), alloc];
    let panel: id = msg_send![panel,
        initWithContentRect:frame
        styleMask:style
        backing:NSBackingStoreType::NSBackingStoreBuffered
        defer:NO
    ];

    // Configure panel properties
    let _: () = msg_send![panel, setFloatingPanel: YES];
    let _: () = msg_send![panel, setLevel: 25i64]; // kCGMaximumWindowLevel - very high
    let _: () = msg_send![panel, setHidesOnDeactivate: NO]; // Stay visible when clicking other windows
    let _: () = msg_send![panel, setOpaque: NO];
    let clear_color: id = msg_send![class!(NSColor), clearColor];
    let _: () = msg_send![panel, setBackgroundColor: clear_color];
    let _: () = msg_send![panel, setHasShadow: YES];
    let _: () = msg_send![panel, setMovableByWindowBackground: YES];

    // Appear on all spaces
    let behavior = NSWindowCollectionBehavior::NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehavior::NSWindowCollectionBehaviorFullScreenAuxiliary;
    panel.setCollectionBehavior_(behavior);

    panel
}

#[allow(deprecated)]
unsafe fn position_panel(panel: id) {
    let screen: id = msg_send![class!(NSScreen), mainScreen];
    let screen_frame: NSRect = msg_send![screen, visibleFrame];

    let x = screen_frame.origin.x + (screen_frame.size.width - WINDOW_WIDTH) / 2.0;
    let y = screen_frame.origin.y + 20.0;

    let origin = NSPoint::new(x, y);
    let _: () = msg_send![panel, setFrameOrigin: origin];
}

fn register_level_view_class() {
    let superclass = class!(NSView);
    let mut decl = ClassDecl::new("LevelMeterView", superclass).unwrap();

    unsafe {
        decl.add_method(
            sel!(drawRect:),
            draw_rect as extern "C" fn(&Object, Sel, NSRect),
        );
        decl.add_method(
            sel!(isOpaque),
            is_opaque as extern "C" fn(&Object, Sel) -> bool,
        );
        decl.add_method(
            sel!(refresh:),
            refresh as extern "C" fn(&Object, Sel, id),
        );
    }

    decl.register();
}

extern "C" fn refresh(this: &Object, _sel: Sel, _timer: id) {
    unsafe {
        let _: () = msg_send![this, setNeedsDisplay: YES];
    }
}

extern "C" fn is_opaque(_this: &Object, _sel: Sel) -> bool {
    false
}

extern "C" fn draw_rect(_this: &Object, _sel: Sel, _rect: NSRect) {
    unsafe {
        let context: id = msg_send![class!(NSGraphicsContext), currentContext];
        let cg_context_ptr: *mut std::ffi::c_void = msg_send![context, CGContext];
        if cg_context_ptr.is_null() {
            return;
        }

        let ctx = CGContext::from_existing_context_ptr(cg_context_ptr as *mut _);
        let level = get_audio_level();

        // Draw background (dark rounded rect)
        ctx.set_rgb_fill_color(0.0, 0.0, 0.0, 0.7);
        add_rounded_rect(&ctx, 0.0, 0.0, WINDOW_WIDTH, WINDOW_HEIGHT, CORNER_RADIUS);
        ctx.fill_path();

        // Draw level meter bar
        let bar_x = PADDING + 14.0; // Leave room for indicator
        let bar_y = PADDING;
        let max_bar_width = WINDOW_WIDTH - PADDING * 2.0 - 16.0;
        let bar_width = max_bar_width * level as f64;
        let bar_height = WINDOW_HEIGHT - PADDING * 2.0;

        if bar_width > 0.0 {
            // Gradient based on level
            let (r, g, b) = level_to_color(level);
            ctx.set_rgb_fill_color(r, g, b, 1.0);
            add_rounded_rect(&ctx, bar_x, bar_y, bar_width, bar_height, CORNER_RADIUS - 2.0);
            ctx.fill_path();
        }

        // Draw recording indicator (pulsing red dot)
        let pulse = ((std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as f64
            / 500.0)
            .sin()
            + 1.0)
            / 2.0;
        let alpha = 0.4 + pulse * 0.6;

        ctx.set_rgb_fill_color(1.0, 0.0, 0.0, alpha);
        let dot_x = PADDING + 3.0;
        let dot_y = (WINDOW_HEIGHT - 8.0) / 2.0;
        ctx.fill_ellipse_in_rect(CGRect::new(&CGPoint::new(dot_x, dot_y), &CGSize::new(8.0, 8.0)));
    }
}

fn add_rounded_rect(ctx: &CGContext, x: f64, y: f64, width: f64, height: f64, radius: f64) {
    let radius = radius.min(width / 2.0).min(height / 2.0);

    ctx.move_to_point(x + radius, y);
    ctx.add_line_to_point(x + width - radius, y);
    ctx.add_quad_curve_to_point(x + width, y, x + width, y + radius);
    ctx.add_line_to_point(x + width, y + height - radius);
    ctx.add_quad_curve_to_point(x + width, y + height, x + width - radius, y + height);
    ctx.add_line_to_point(x + radius, y + height);
    ctx.add_quad_curve_to_point(x, y + height, x, y + height - radius);
    ctx.add_line_to_point(x, y + radius);
    ctx.add_quad_curve_to_point(x, y, x + radius, y);
    ctx.close_path();
}

fn level_to_color(level: f32) -> (f64, f64, f64) {
    if level < 0.5 {
        // Green
        (0.0, 0.8, 0.0)
    } else if level < 0.75 {
        // Yellow
        let t = (level - 0.5) / 0.25;
        (t as f64, 0.8, 0.0)
    } else {
        // Red
        let t = (level - 0.75) / 0.25;
        (1.0, 0.8 * (1.0 - t as f64), 0.0)
    }
}

#[allow(deprecated)]
unsafe fn create_level_view() -> id {
    let view_class = class!(LevelMeterView);
    let frame = NSRect::new(NSPoint::new(0.0, 0.0), NSSize::new(WINDOW_WIDTH, WINDOW_HEIGHT));
    let view: id = msg_send![view_class, alloc];
    let view: id = msg_send![view, initWithFrame: frame];
    view
}

fn capture_audio() {
    let host = cpal::default_host();

    let device = match host.default_input_device() {
        Some(d) => d,
        None => return,
    };

    let config = match device.default_input_config() {
        Ok(c) => c,
        Err(_) => return,
    };

    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => build_stream::<f32>(&device, &config.into()),
        cpal::SampleFormat::I16 => build_stream::<i16>(&device, &config.into()),
        cpal::SampleFormat::U16 => build_stream::<u16>(&device, &config.into()),
        _ => return,
    };

    if let Ok(stream) = stream {
        if stream.play().is_ok() {
            while RUNNING.load(Ordering::SeqCst) {
                thread::sleep(Duration::from_millis(100));
            }
            // Explicitly pause before drop to release microphone
            let _ = stream.pause();
        }
    }
}

fn build_stream<T: cpal::Sample + cpal::SizedSample>(
    device: &cpal::Device,
    config: &cpal::StreamConfig,
) -> Result<cpal::Stream, cpal::BuildStreamError>
where
    f32: cpal::FromSample<T>,
{
    device.build_input_stream(
        config,
        move |data: &[T], _: &cpal::InputCallbackInfo| {
            if !RUNNING.load(Ordering::SeqCst) {
                return;
            }

            // Calculate RMS level
            let sum: f32 = data
                .iter()
                .map(|s| {
                    let sample: f32 = cpal::Sample::from_sample(*s);
                    sample * sample
                })
                .sum();
            let rms = (sum / data.len() as f32).sqrt();

            // Convert to 0-1 range with some amplification
            let level = (rms * 5.0).min(1.0);

            // Smooth the level
            let current = get_audio_level();
            set_audio_level(current * 0.3 + level * 0.7);
        },
        |_err| {},
        None,
    )
}

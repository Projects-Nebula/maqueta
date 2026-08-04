    (() => {
      "use strict";

      const paletteCatalog = (() => {
        const element = document.getElementById("palette-catalog");
        if (!element) return { roles: [], presets: [], user_palettes: [] };
        try {
          const parsed = JSON.parse(element.textContent || "{}");
          return {
            roles: Array.isArray(parsed.roles) ? parsed.roles : [],
            presets: Array.isArray(parsed.presets) ? parsed.presets : [],
            user_palettes: Array.isArray(parsed.user_palettes) ? parsed.user_palettes : []
          };
        } catch {
          return { roles: [], presets: [], user_palettes: [] };
        }
      })();

      // The server catalog is the source of truth. This fallback only keeps
      // the standalone editor shell usable in fixture pages without context.
      const paletteRoles = paletteCatalog.roles.length
        ? paletteCatalog.roles
        : [
            { id: "primary", variable: "--color-primary", label: "Principal" },
            { id: "background", variable: "--color-background", label: "Fondo" },
            { id: "text", variable: "--color-text", label: "Texto" },
            { id: "surface", variable: "--color-surface", label: "Superficie" }
          ];
      const palettePresets = paletteCatalog.presets;
      const userPalettes = paletteCatalog.user_palettes;

      const defaultPage = {
        schemaVersion: "2.0",
        settings: {
          strict: true,
          escapeText: true,
          allowRawHtml: false,
          allowInlineScripts: false,
          requireImageAlt: true,
          requireUniqueIds: true
        },
        document: {
          doctype: "html",
          htmlAttributes: {
            lang: "es",
            dir: "ltr"
          },
          head: {
            title: "Landing page de ejemplo",
            metas: [
              { charset: "UTF-8" },
              { name: "viewport", content: "width=device-width, initial-scale=1" },
              {
                name: "description",
                content: "Una landing page creada desde un editor visual basado en JSON."
              }
            ],
            links: [],
            scripts: []
          },
          body: {
            attributes: {
              class: ["page"]
            },
            children: [
              {
                type: "element",
                tag: "header",
                attributes: {
                  class: ["site-header"]
                },
                children: [
                  {
                    type: "element",
                    tag: "div",
                    attributes: {
                      class: ["container", "nav"]
                    },
                    children: [
                      {
                        type: "element",
                        tag: "a",
                        attributes: {
                          class: ["brand"],
                          href: "#"
                        },
                        children: [
                          { type: "text", value: "Nova" }
                        ]
                      },
                      {
                        type: "element",
                        tag: "a",
                        attributes: {
                          class: ["button", "button-small"],
                          href: "#contacto"
                        },
                        children: [
                          { type: "text", value: "Comenzar" }
                        ]
                      }
                    ]
                  }
                ]
              },
              {
                type: "element",
                tag: "main",
                attributes: {
                  class: ["main-content"]
                },
                children: [
                  {
                    type: "element",
                    tag: "section",
                    attributes: {
                      id: "hero",
                      class: ["hero"]
                    },
                    children: [
                      {
                        type: "element",
                        tag: "div",
                        attributes: {
                          class: ["container", "hero-grid"]
                        },
                        children: [
                          {
                            type: "element",
                            tag: "div",
                            attributes: {
                              class: ["hero-copy"]
                            },
                            children: [
                              {
                                type: "element",
                                tag: "span",
                                attributes: {
                                  class: ["eyebrow"]
                                },
                                children: [
                                  { type: "text", value: "NUEVA PLATAFORMA" }
                                ]
                              },
                              {
                                type: "element",
                                tag: "h1",
                                attributes: {
                                  class: ["hero-title"]
                                },
                                children: [
                                  { type: "text", value: "Crea experiencias digitales que convierten" }
                                ]
                              },
                              {
                                type: "element",
                                tag: "p",
                                attributes: {
                                  class: ["hero-description"]
                                },
                                children: [
                                  {
                                    type: "text",
                                    value: "Diseña una landing profesional, personaliza cada detalle y exporta su estructura en JSON."
                                  }
                                ]
                              },
                              {
                                type: "element",
                                tag: "div",
                                attributes: {
                                  class: ["hero-actions"]
                                },
                                children: [
                                  {
                                    type: "element",
                                    tag: "a",
                                    attributes: {
                                      class: ["button"],
                                      href: "#beneficios"
                                    },
                                    children: [
                                      { type: "text", value: "Ver beneficios" }
                                    ]
                                  },
                                  {
                                    type: "element",
                                    tag: "a",
                                    attributes: {
                                      class: ["button", "button-secondary"],
                                      href: "#contacto"
                                    },
                                    children: [
                                      { type: "text", value: "Hablar con ventas" }
                                    ]
                                  }
                                ]
                              }
                            ]
                          },
                          {
                            type: "element",
                            tag: "div",
                            attributes: {
                              class: ["hero-visual"]
                            },
                            children: [
                              {
                                type: "element",
                                tag: "div",
                                attributes: {
                                  class: ["mockup-card"]
                                },
                                children: [
                                  {
                                    type: "element",
                                    tag: "span",
                                    attributes: {
                                      class: ["mockup-label"]
                                    },
                                    children: [
                                      { type: "text", value: "Conversiones" }
                                    ]
                                  },
                                  {
                                    type: "element",
                                    tag: "strong",
                                    attributes: {
                                      class: ["mockup-number"]
                                    },
                                    children: [
                                      { type: "text", value: "+38%" }
                                    ]
                                  },
                                  {
                                    type: "element",
                                    tag: "div",
                                    attributes: {
                                      class: ["mockup-chart"]
                                    },
                                    children: []
                                  }
                                ]
                              }
                            ]
                          }
                        ]
                      }
                    ]
                  },
                  {
                    type: "element",
                    tag: "section",
                    attributes: {
                      id: "beneficios",
                      class: ["features"]
                    },
                    children: [
                      {
                        type: "element",
                        tag: "div",
                        attributes: {
                          class: ["container"]
                        },
                        children: [
                          {
                            type: "element",
                            tag: "h2",
                            attributes: {
                              class: ["section-title"]
                            },
                            children: [
                              { type: "text", value: "Todo lo que necesitas para empezar" }
                            ]
                          },
                          {
                            type: "element",
                            tag: "div",
                            attributes: {
                              class: ["feature-grid"]
                            },
                            children: [
                              {
                                type: "element",
                                tag: "article",
                                attributes: {
                                  class: ["feature-card"]
                                },
                                children: [
                                  {
                                    type: "element",
                                    tag: "span",
                                    attributes: { class: ["feature-icon"] },
                                    children: [{ type: "text", value: "✦" }]
                                  },
                                  {
                                    type: "element",
                                    tag: "h3",
                                    attributes: {},
                                    children: [{ type: "text", value: "Editor visual" }]
                                  },
                                  {
                                    type: "element",
                                    tag: "p",
                                    attributes: {},
                                    children: [{ type: "text", value: "Modifica textos, colores y estructura sin escribir JSON." }]
                                  }
                                ]
                              },
                              {
                                type: "element",
                                tag: "article",
                                attributes: {
                                  class: ["feature-card"]
                                },
                                children: [
                                  {
                                    type: "element",
                                    tag: "span",
                                    attributes: { class: ["feature-icon"] },
                                    children: [{ type: "text", value: "⚡" }]
                                  },
                                  {
                                    type: "element",
                                    tag: "h3",
                                    attributes: {},
                                    children: [{ type: "text", value: "Vista en vivo" }]
                                  },
                                  {
                                    type: "element",
                                    tag: "p",
                                    attributes: {},
                                    children: [{ type: "text", value: "Cada cambio se refleja inmediatamente en la previsualización." }]
                                  }
                                ]
                              },
                              {
                                type: "element",
                                tag: "article",
                                attributes: {
                                  class: ["feature-card"]
                                },
                                children: [
                                  {
                                    type: "element",
                                    tag: "span",
                                    attributes: { class: ["feature-icon"] },
                                    children: [{ type: "text", value: "↓" }]
                                  },
                                  {
                                    type: "element",
                                    tag: "h3",
                                    attributes: {},
                                    children: [{ type: "text", value: "Exportación sencilla" }]
                                  },
                                  {
                                    type: "element",
                                    tag: "p",
                                    attributes: {},
                                    children: [{ type: "text", value: "Descarga el JSON final y úsalo en tu generador de HTML." }]
                                  }
                                ]
                              }
                            ]
                          }
                        ]
                      }
                    ]
                  },
                  {
                    type: "element",
                    tag: "section",
                    attributes: {
                      id: "contacto",
                      class: ["cta"]
                    },
                    children: [
                      {
                        type: "element",
                        tag: "div",
                        attributes: {
                          class: ["container", "cta-box"]
                        },
                        children: [
                          {
                            type: "element",
                            tag: "h2",
                            attributes: {},
                            children: [{ type: "text", value: "Convierte tu idea en una página real" }]
                          },
                          {
                            type: "element",
                            tag: "p",
                            attributes: {},
                            children: [{ type: "text", value: "Personaliza este ejemplo y descarga tu configuración cuando esté lista." }]
                          },
                          {
                            type: "element",
                            tag: "a",
                            attributes: {
                              class: ["button", "button-light"],
                              href: "#"
                            },
                            children: [{ type: "text", value: "Crear mi página" }]
                          }
                        ]
                      }
                    ]
                  }
                ]
              },
              {
                type: "element",
                tag: "footer",
                attributes: {
                  class: ["footer"]
                },
                children: [
                  {
                    type: "element",
                    tag: "div",
                    attributes: {
                      class: ["container", "footer-row"]
                    },
                    children: [
                      { type: "element", tag: "strong", attributes: {}, children: [{ type: "text", value: "Nova" }] },
                      { type: "element", tag: "span", attributes: {}, children: [{ type: "text", value: "© 2026. Todos los derechos reservados." }] }
                    ]
                  }
                ]
              }
            ]
          }
        },
        styles: {
          variables: {
            "--color-primary": "#5b5ce2",
            "--color-background": "#f7f8fc",
            "--color-text": "#182034",
            "--color-surface": "#ffffff",
            "--font-primary": "Inter, Arial, sans-serif",
            "--max-width": "1120px",
            "--radius": "20px",
            "--section-spacing": "88px"
          },
          rules: [
            {
              selector: "*",
              declarations: {
                "box-sizing": "border-box"
              }
            },
            {
              selector: "html",
              declarations: {
                "scroll-behavior": "smooth"
              }
            },
            {
              selector: "body",
              declarations: {
                margin: "0",
                color: "var(--color-text)",
                background: "var(--color-background)",
                "font-family": "var(--font-primary)",
                "line-height": "1.6"
              }
            },
            {
              selector: "a",
              declarations: {
                color: "inherit",
                "text-decoration": "none"
              }
            },
            {
              selector: ".container",
              declarations: {
                width: "min(calc(100% - 40px), var(--max-width))",
                margin: "0 auto"
              }
            },
            {
              selector: ".site-header",
              declarations: {
                position: "sticky",
                top: "0",
                "z-index": "20",
                background: "rgba(247,248,252,.92)",
                "backdrop-filter": "blur(14px)",
                "border-bottom": "1px solid rgba(24,32,52,.08)"
              }
            },
            {
              selector: ".nav",
              declarations: {
                height: "72px",
                display: "flex",
                "align-items": "center",
                "justify-content": "space-between"
              }
            },
            {
              selector: ".brand",
              declarations: {
                "font-size": "22px",
                "font-weight": "900",
                "letter-spacing": "-.04em"
              }
            },
            {
              selector: ".hero",
              declarations: {
                padding: "110px 0 var(--section-spacing)"
              }
            },
            {
              selector: ".hero-grid",
              declarations: {
                display: "grid",
                "grid-template-columns": "1.15fr .85fr",
                gap: "70px",
                "align-items": "center"
              }
            },
            {
              selector: ".eyebrow",
              declarations: {
                display: "inline-flex",
                padding: "7px 11px",
                color: "var(--color-primary)",
                background: "color-mix(in srgb, var(--color-primary) 10%, white)",
                "border-radius": "999px",
                "font-size": "12px",
                "font-weight": "800",
                "letter-spacing": ".08em"
              }
            },
            {
              selector: ".hero-title",
              declarations: {
                margin: "20px 0 18px",
                "max-width": "720px",
                "font-size": "clamp(42px, 7vw, 78px)",
                "line-height": ".98",
                "letter-spacing": "-.055em"
              }
            },
            {
              selector: ".hero-description",
              declarations: {
                margin: "0",
                "max-width": "640px",
                color: "#59647a",
                "font-size": "19px"
              }
            },
            {
              selector: ".hero-actions",
              declarations: {
                margin: "30px 0 0",
                display: "flex",
                gap: "12px",
                "flex-wrap": "wrap"
              }
            },
            {
              selector: ".button",
              declarations: {
                display: "inline-flex",
                "align-items": "center",
                "justify-content": "center",
                padding: "13px 20px",
                color: "white",
                background: "var(--color-primary)",
                border: "1px solid var(--color-primary)",
                "border-radius": "12px",
                "font-weight": "800"
              }
            },
            {
              selector: ".button-small",
              declarations: {
                padding: "9px 15px",
                "font-size": "14px"
              }
            },
            {
              selector: ".button-secondary",
              declarations: {
                color: "var(--color-text)",
                background: "transparent",
                "border-color": "rgba(24,32,52,.2)"
              }
            },
            {
              selector: ".hero-visual",
              declarations: {
                display: "grid",
                "place-items": "center"
              }
            },
            {
              selector: ".mockup-card",
              declarations: {
                width: "min(100%, 390px)",
                padding: "34px",
                background: "linear-gradient(145deg, #1d2440, #11172a)",
                "border-radius": "var(--radius)",
                "box-shadow": "0 35px 80px rgba(29,36,64,.25)",
                color: "white",
                transform: "rotate(3deg)"
              }
            },
            {
              selector: ".mockup-label",
              declarations: {
                display: "block",
                color: "#aeb7d7",
                "font-size": "14px"
              }
            },
            {
              selector: ".mockup-number",
              declarations: {
                display: "block",
                margin: "6px 0 25px",
                "font-size": "52px",
                "line-height": "1"
              }
            },
            {
              selector: ".mockup-chart",
              declarations: {
                height: "150px",
                background: "linear-gradient(135deg, transparent 0 15%, #7778ff 16% 22%, transparent 23% 36%, #7778ff 37% 45%, transparent 46% 59%, #7778ff 60% 69%, transparent 70% 82%, #7778ff 83% 92%, transparent 93%)",
                opacity: ".9",
                "border-bottom": "1px solid rgba(255,255,255,.18)"
              }
            },
            {
              selector: ".features",
              declarations: {
                padding: "var(--section-spacing) 0"
              }
            },
            {
              selector: ".section-title",
              declarations: {
                margin: "0 0 36px",
                "max-width": "650px",
                "font-size": "clamp(32px, 5vw, 50px)",
                "line-height": "1.05",
                "letter-spacing": "-.04em"
              }
            },
            {
              selector: ".feature-grid",
              declarations: {
                display: "grid",
                "grid-template-columns": "repeat(3, 1fr)",
                gap: "18px"
              }
            },
            {
              selector: ".feature-card",
              declarations: {
                padding: "28px",
                background: "var(--color-surface)",
                border: "1px solid rgba(24,32,52,.08)",
                "border-radius": "var(--radius)",
                "box-shadow": "0 16px 40px rgba(24,32,52,.06)"
              }
            },
            {
              selector: ".feature-card h3",
              declarations: {
                margin: "16px 0 7px",
                "font-size": "20px"
              }
            },
            {
              selector: ".feature-card p",
              declarations: {
                margin: "0",
                color: "#657087"
              }
            },
            {
              selector: ".feature-icon",
              declarations: {
                width: "42px",
                height: "42px",
                display: "grid",
                "place-items": "center",
                color: "var(--color-primary)",
                background: "color-mix(in srgb, var(--color-primary) 10%, white)",
                "border-radius": "12px",
                "font-size": "20px"
              }
            },
            {
              selector: ".cta",
              declarations: {
                padding: "var(--section-spacing) 0"
              }
            },
            {
              selector: ".cta-box",
              declarations: {
                padding: "65px",
                color: "white",
                background: "var(--color-primary)",
                "border-radius": "calc(var(--radius) + 8px)",
                "text-align": "center"
              }
            },
            {
              selector: ".cta-box h2",
              declarations: {
                margin: "0",
                "font-size": "clamp(34px, 5vw, 56px)",
                "line-height": "1.05",
                "letter-spacing": "-.04em"
              }
            },
            {
              selector: ".cta-box p",
              declarations: {
                "max-width": "650px",
                margin: "18px auto 28px",
                opacity: ".88"
              }
            },
            {
              selector: ".button-light",
              declarations: {
                color: "var(--color-primary)",
                background: "white",
                "border-color": "white"
              }
            },
            {
              selector: ".footer",
              declarations: {
                padding: "34px 0",
                background: "var(--color-surface)",
                "border-top": "1px solid rgba(24,32,52,.08)"
              }
            },
            {
              selector: ".footer-row",
              declarations: {
                display: "flex",
                "justify-content": "space-between",
                gap: "20px",
                color: "#657087"
              }
            }
          ],
          mediaQueries: [
            {
              query: "(max-width: 760px)",
              rules: [
                {
                  selector: ".hero",
                  declarations: {
                    padding: "72px 0 var(--section-spacing)"
                  }
                },
                {
                  selector: ".hero-grid",
                  declarations: {
                    "grid-template-columns": "1fr",
                    gap: "42px"
                  }
                },
                {
                  selector: ".feature-grid",
                  declarations: {
                    "grid-template-columns": "1fr"
                  }
                },
                {
                  selector: ".cta-box",
                  declarations: {
                    padding: "42px 24px"
                  }
                },
                {
                  selector: ".footer-row",
                  declarations: {
                    "flex-direction": "column"
                  }
                }
              ]
            }
          ],
          keyframes: []
        },
        components: {},
        assets: {}
      };

      let state = clone(defaultPage);
      let paletteBaseline = null;
      let selectedPath = null;
      let toastTimer = null;
      let previewReady = false;
      let previewUpdateTimer = null;
      let previewLoadToken = 0;

      const HISTORY_LIMIT = 100;
      const HISTORY_DEBOUNCE_MS = 450;
      let historyPast = [JSON.stringify(state)];
      let historyFuture = [];
      let historyCommitTimer = null;
      let isRestoringHistory = false;

      let draggedTreePath = null;
      let activeDropRow = null;
      let activeDropPosition = null;

      let draggedPreviewPath = null;
      let activePreviewDropElement = null;
      let activePreviewDropPosition = null;
      let activePreviewDropPath = null;
      let previewDraggedElement = null;
      let previewDropCommitted = false;

      const els = {
        tabs: [...document.querySelectorAll(".tab[data-tab]")],
        panels: [...document.querySelectorAll(".tab-panel[data-panel]")],
        previewFrame: document.getElementById("previewFrame"),
        previewWrap: document.getElementById("previewWrap"),
        tree: document.getElementById("tree"),
        inspector: document.getElementById("inspector"),
        jsonEditor: document.getElementById("jsonEditor"),
        jsonError: document.getElementById("jsonError"),
        toast: document.getElementById("toast"),
        fileInput: document.getElementById("fileInput"),
        undoButton: document.getElementById("undoButton"),
        redoButton: document.getElementById("redoButton")
      };

      function ensureStyleShape(target) {
        if (!target.styles || typeof target.styles !== "object" || Array.isArray(target.styles)) {
          target.styles = {};
        }
        if (
          !target.styles.variables ||
          typeof target.styles.variables !== "object" ||
          Array.isArray(target.styles.variables)
        ) {
          target.styles.variables = {};
        }
        if (!Array.isArray(target.styles.rules)) target.styles.rules = [];
        if (!Array.isArray(target.styles.mediaQueries)) target.styles.mediaQueries = [];
        if (!Array.isArray(target.styles.keyframes)) target.styles.keyframes = [];
        return target;
      }

      function capturePaletteSnapshot(sourceState = state) {
        ensureStyleShape(sourceState);
        const variables = {};
        paletteRoles.forEach(role => {
          if (sourceState.styles.variables[role.variable] !== undefined) {
            variables[role.variable] = sourceState.styles.variables[role.variable];
          }
        });
        return {
          variables,
          palette: sourceState.styles.palette ? clone(sourceState.styles.palette) : null
        };
      }

      function isHexColor(value) {
        return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value.trim());
      }

      function getPalettePreset(id) {
        return palettePresets.find(preset => preset.id === id) || null;
      }

      function getUserPalette(id) {
        return userPalettes.find(palette => palette.id === id) || null;
      }

      function paletteValuesMatch(preset, variables) {
        return paletteRoles.every(role => variables[role.variable] === preset.variables[role.variable]);
      }

      function paletteSlug(value) {
        const slug = String(value || "")
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, "")
          .slice(0, 56);
        return slug || "custom";
      }

      function currentPaletteDescriptor() {
        ensureStyleShape(state);
        const variables = state.styles.variables;
        const metadata = state.styles.palette;
        if (metadata?.source === "preset") {
          const preset = getPalettePreset(metadata.id);
          if (preset && paletteValuesMatch(preset, variables)) return preset;
        }
        if (metadata?.source === "ai") {
          return {
            id: "ai",
            name: metadata.name || "Generada por IA",
            description: "Colores generados para esta página por el asistente.",
            source: "ai",
            variables
          };
        }
        if (metadata?.source === "custom") {
          const saved = getUserPalette(metadata.id);
          if (saved && paletteValuesMatch(saved, variables)) return saved;
        }
        return {
          id: "custom",
          name: metadata?.name || "Personalizada",
          description: "Ajustá cada color para crear una identidad propia.",
          source: "custom",
          variables
        };
      }

      function paletteContrastRatio(first, second) {
        if (!isHexColor(first) || !isHexColor(second)) return null;
        const toLinear = channel => {
          const value = channel / 255;
          return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
        };
        const rgb = hex => [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
        const luminance = hex => {
          const [red, green, blue] = rgb(hex).map(toLinear);
          return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
        };
        const light = Math.max(luminance(first), luminance(second));
        const dark = Math.min(luminance(first), luminance(second));
        return (light + 0.05) / (dark + 0.05);
      }

      function formatContrast(value) {
        return value === null ? "—" : `${value.toFixed(1)}:1`;
      }

      function setPaletteFeedback(message, tone = "info") {
        const feedback = document.getElementById("paletteContrast");
        if (!feedback) return;
        feedback.textContent = message;
        feedback.dataset.tone = tone;
      }

      function renderPaletteControls() {
        const select = document.getElementById("palettePresetSelect");
        if (!select) return;
        const descriptor = currentPaletteDescriptor();
        const metadata = state.styles.palette;
        const selectedValue = descriptor.source === "preset"
          ? descriptor.id
          : descriptor.source === "ai"
            ? "ai"
            : descriptor.user_palette_id
              ? descriptor.id
              : "custom";
        select.value = Array.from(select.options).some(option => option.value === selectedValue)
          ? selectedValue
          : "custom";
        const status = document.getElementById("paletteStatus");
        if (status) status.textContent = descriptor.name;
        const nameInput = document.getElementById("paletteName");
        if (nameInput && document.activeElement !== nameInput) nameInput.value = descriptor.name;
        const description = document.getElementById("paletteDescription");
        if (description) description.textContent = descriptor.description;

        const swatches = document.getElementById("paletteSwatches");
        if (swatches) {
          swatches.replaceChildren();
          paletteRoles.forEach(role => {
            const item = document.createElement("span");
            item.className = "palette-swatch-item";
            item.setAttribute("role", "listitem");
            const color = document.createElement("span");
            color.className = "palette-swatch";
            const value = state.styles.variables[role.variable];
            if (isHexColor(value)) color.style.backgroundColor = value;
            color.setAttribute("aria-hidden", "true");
            const label = document.createElement("span");
            label.className = "palette-swatch-copy";
            label.textContent = `${role.label} ${isHexColor(value) ? value.toUpperCase() : "inválido"}`;
            item.append(color, label);
            swatches.appendChild(item);
          });
        }

        const background = state.styles.variables["--color-background"];
        const text = state.styles.variables["--color-text"];
        const primary = state.styles.variables["--color-primary"];
        const surface = state.styles.variables["--color-surface"];
        const textBackground = paletteContrastRatio(text, background);
        const primarySurface = paletteContrastRatio(primary, surface);
        const passes = textBackground !== null && textBackground >= 4.5 && primarySurface !== null && primarySurface >= 3;
        setPaletteFeedback(
          passes
            ? `Contraste recomendado · texto/fondo ${formatContrast(textBackground)} · principal/superficie ${formatContrast(primarySurface)}.`
            : `Revisá el contraste · texto/fondo ${formatContrast(textBackground)} · principal/superficie ${formatContrast(primarySurface)}. Se recomienda 4.5:1 para texto y 3:1 para controles.`,
          passes ? "success" : "warning"
        );
        if (metadata?.source === "ai" && selectedValue === "ai") {
          select.title = "La paleta fue generada por IA; podés personalizarla con los controles de abajo.";
        } else {
          select.removeAttribute("title");
        }
        const deleteButton = document.getElementById("paletteDeleteButton");
        if (deleteButton) deleteButton.hidden = !descriptor.user_palette_id;
      }

      function populatePaletteSelect() {
        const select = document.getElementById("palettePresetSelect");
        if (!select) return;
        palettePresets.forEach(preset => {
          if (Array.from(select.options).some(option => option.value === preset.id)) return;
          const option = document.createElement("option");
          option.value = preset.id;
          option.textContent = preset.name;
          select.appendChild(option);
        });
        select.querySelector('optgroup[data-user-palettes="true"]')?.remove();
        if (userPalettes.length) {
          const group = document.createElement("optgroup");
          group.label = "Mis paletas";
          group.dataset.userPalettes = "true";
          userPalettes.forEach(palette => {
            const option = document.createElement("option");
            option.value = palette.id;
            option.textContent = palette.name;
            group.appendChild(option);
          });
          select.appendChild(group);
        }
      }

      function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
      }

      function markPaletteCustom(name) {
        ensureStyleShape(state);
        const customName = String(name || state.styles.palette?.name || "Personalizada")
          .replace(/[\u0000-\u001f\u007f]/g, "")
          .trim()
          .slice(0, 80) || "Personalizada";
        state.styles.palette = {
          id: paletteSlug(customName),
          name: customName,
          source: "custom"
        };
      }

      function applyPalette(paletteId) {
        const palette = getPalettePreset(paletteId) || getUserPalette(paletteId);
        if (!palette || !paletteValuesMatch(palette, palette.variables)) return false;
        flushHistoryCommit();
        ensureStyleShape(state);
        paletteRoles.forEach(role => {
          state.styles.variables[role.variable] = palette.variables[role.variable];
        });
        state.styles.palette = {
          id: palette.id,
          name: palette.name,
          source: palette.source
        };
        updateAll({ skipHistory: true });
        commitHistorySnapshot();
        showToast(`Paleta ${palette.name} aplicada.`, "success");
        return true;
      }

      function resetPalette() {
        if (!paletteBaseline) return false;
        flushHistoryCommit();
        ensureStyleShape(state);
        paletteRoles.forEach(role => {
          const value = paletteBaseline.variables[role.variable];
          if (value === undefined) delete state.styles.variables[role.variable];
          else state.styles.variables[role.variable] = value;
        });
        if (paletteBaseline.palette) state.styles.palette = clone(paletteBaseline.palette);
        else delete state.styles.palette;
        updateAll({ skipHistory: true });
        commitHistorySnapshot();
        showToast("Paleta restablecida.", "success");
        return true;
      }

      async function saveUserPalette() {
        const button = document.getElementById("paletteSaveButton");
        const nameInput = document.getElementById("paletteName");
        const name = String(nameInput?.value || "Mi paleta")
          .replace(/[\u0000-\u001f\u007f]/g, "")
          .trim()
          .slice(0, 80) || "Mi paleta";
        const variables = {};
        for (const role of paletteRoles) {
          const value = state.styles?.variables?.[role.variable];
          if (!isHexColor(value)) {
            setPaletteFeedback("Completá los cuatro colores con valores HEX de seis dígitos antes de guardar.", "error");
            return;
          }
          variables[role.variable] = value;
        }
        if (button) {
          button.disabled = true;
          button.textContent = "Guardando…";
        }
        try {
          const response = await fetch("/api/user-palettes/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({ name, variables }),
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(data.detail || "save failed");
          const entry = {
            id: data.slug,
            name: data.name,
            description: "Paleta guardada por vos para reutilizarla en otros templates.",
            source: "custom",
            variables: data.variables,
            user_palette_id: data.id,
          };
          if (!entry.id || !paletteValuesMatch(entry, variables)) throw new Error("invalid palette response");
          userPalettes.push(entry);
          state.styles.palette = { id: entry.id, name: entry.name, source: "custom" };
          populatePaletteSelect();
          updateAll({ skipHistory: true });
          commitHistorySnapshot();
          showToast(`Paleta ${entry.name} guardada.`, "success");
        } catch (error) {
          setPaletteFeedback("No se pudo guardar la paleta. Intentá de nuevo.", "error");
        } finally {
          if (button) {
            button.disabled = false;
            button.textContent = "Guardar en mis paletas";
          }
        }
      }

      async function deleteUserPalette() {
        const descriptor = currentPaletteDescriptor();
        if (!descriptor.user_palette_id) return;
        const button = document.getElementById("paletteDeleteButton");
        if (button) button.disabled = true;
        try {
          const response = await fetch(
            `/api/user-palettes/${encodeURIComponent(descriptor.user_palette_id)}/`,
            {
              method: "DELETE",
              credentials: "same-origin",
              headers: { "X-CSRFToken": getCsrfToken() },
            },
          );
          if (!response.ok) throw new Error("delete failed");
          const index = userPalettes.findIndex(item => item.user_palette_id === descriptor.user_palette_id);
          if (index >= 0) userPalettes.splice(index, 1);
          populatePaletteSelect();
          markPaletteCustom(descriptor.name);
          updateAll({ skipHistory: true });
          commitHistorySnapshot();
          showToast(`Paleta ${descriptor.name} eliminada del catálogo.`, "success");
        } catch (error) {
          setPaletteFeedback("No se pudo eliminar la paleta. Intentá de nuevo.", "error");
          if (button) button.disabled = false;
        }
      }

      function clone(value) {
        return JSON.parse(JSON.stringify(value));
      }

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function escapeAttribute(value) {
        return escapeHtml(value);
      }

      function showToast(message, tone = "info") {
        clearTimeout(toastTimer);
        els.toast.textContent = message;
        els.toast.dataset.tone = tone;
        els.toast.setAttribute("role", tone === "error" ? "alert" : "status");
        els.toast.setAttribute("aria-live", tone === "error" ? "assertive" : "polite");
        els.toast.classList.add("visible");
        const timeout = tone === "error" ? 5600 : tone === "success" ? 3200 : 3800;
        toastTimer = setTimeout(() => els.toast.classList.remove("visible"), timeout);
      }

      function updateHistoryButtons() {
        els.undoButton.disabled = historyPast.length <= 1;
        els.redoButton.disabled = historyFuture.length === 0;
      }

      function commitHistorySnapshot() {
        if (isRestoringHistory) return;

        const snapshot = JSON.stringify(state);
        const previousSnapshot = historyPast.at(-1);

        if (snapshot === previousSnapshot) {
          updateHistoryButtons();
          return;
        }

        historyPast.push(snapshot);

        if (historyPast.length > HISTORY_LIMIT) {
          historyPast.shift();
        }

        historyFuture = [];
        updateHistoryButtons();
        // A consumer-agnostic "state changed" signal (autosave.js listens for
        // this) — fires whenever a snapshot actually lands in history, so it
        // naturally follows the same debounce/immediate-flush timing.
        document.dispatchEvent(new CustomEvent("vjpb:state-committed"));
      }

      function scheduleHistoryCommit() {
        if (isRestoringHistory) return;

        clearTimeout(historyCommitTimer);
        historyCommitTimer = setTimeout(
          commitHistorySnapshot,
          HISTORY_DEBOUNCE_MS
        );
      }

      function flushHistoryCommit() {
        clearTimeout(historyCommitTimer);
        historyCommitTimer = null;
        commitHistorySnapshot();
      }

      function restoreHistorySnapshot(snapshot, message) {
        isRestoringHistory = true;

        try {
          state = JSON.parse(snapshot);

          if (selectedPath && !getNode(selectedPath)) {
            selectedPath = null;
          }

          updateAll({
            fullPreview: true,
            skipHistory: true
          });

          showToast(message);
        } finally {
          isRestoringHistory = false;
          updateHistoryButtons();
        }
      }

      function undoChange() {
        flushHistoryCommit();

        if (historyPast.length <= 1) {
          showToast("No hay más cambios para deshacer.");
          return;
        }

        const currentSnapshot = historyPast.pop();
        historyFuture.push(currentSnapshot);

        restoreHistorySnapshot(
          historyPast.at(-1),
          "Cambio deshecho."
        );
      }

      function redoChange() {
        clearTimeout(historyCommitTimer);
        historyCommitTimer = null;

        if (historyFuture.length === 0) {
          showToast("No hay cambios para rehacer.");
          return;
        }

        const nextSnapshot = historyFuture.pop();
        historyPast.push(nextSnapshot);

        restoreHistorySnapshot(
          nextSnapshot,
          "Cambio rehecho."
        );
      }

      function getMeta(name) {
        return state.document.head.metas.find(meta => meta.name === name);
      }

      function ensureMeta(name) {
        let meta = getMeta(name);
        if (!meta) {
          meta = { name, content: "" };
          state.document.head.metas.push(meta);
        }
        return meta;
      }

      function getCanonicalLink() {
        return state.document.head.links.find(link => link.rel === "canonical");
      }

      function ensureCanonicalLink() {
        let link = getCanonicalLink();
        if (!link) {
          link = { rel: "canonical", href: "" };
          state.document.head.links.push(link);
        }
        return link;
      }

      function attributesToString(attributes = {}) {
        const safe = [];
        for (const [rawName, rawValue] of Object.entries(attributes)) {
          const name = String(rawName).trim();
          if (!name || name.toLowerCase().startsWith("on")) continue;
          if (rawValue === null || rawValue === undefined || rawValue === false || rawValue === "") continue;

          let value = rawValue;
          if (name === "class" && Array.isArray(value)) {
            value = value.filter(Boolean).join(" ");
          }

          if (value === true) {
            safe.push(escapeAttribute(name));
          } else {
            safe.push(`${escapeAttribute(name)}="${escapeAttribute(value)}"`);
          }
        }
        return safe.length ? " " + safe.join(" ") : "";
      }

      function renderNode(node, path = [], editorMode = true) {
        if (!node || typeof node !== "object") return "";

        if (node.type === "text") {
          return escapeHtml(node.value ?? "");
        }

        if (node.type !== "element") return "";

        const forbiddenTags = new Set(["script", "object", "embed"]);
        const tag = /^[a-z][a-z0-9-]*$/i.test(node.tag || "") ? node.tag.toLowerCase() : "div";
        if (forbiddenTags.has(tag)) return "";
        // iframe is allowed only for a known video-embed src (mirrors
        // apps/ai_assistant/sanitize.py's IFRAME_SRC_ALLOWED_PREFIXES) —
        // arbitrary iframe src stays blocked in the preview too.
        if (tag === "iframe") {
          const src = String((node.attributes || {}).src || "");
          const allowedIframeSrcPrefixes = [
            "https://www.youtube.com/embed/",
            "https://www.youtube-nocookie.com/embed/",
            "https://player.vimeo.com/video/"
          ];
          if (!allowedIframeSrcPrefixes.some((prefix) => src.startsWith(prefix))) return "";
        }

        const voidTags = new Set(["area", "base", "br", "col", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);

        const renderedAttributes = {
          ...(node.attributes || {})
        };

        if (editorMode) {
          renderedAttributes["data-vjpb-path"] = path.join(".");
        }

        const attrs = attributesToString(renderedAttributes);

        if (voidTags.has(tag)) return `<${tag}${attrs}>`;

        const children = Array.isArray(node.children)
          ? node.children
              .map((child, index) =>
                renderNode(child, [...path, index], editorMode)
              )
              .join("")
          : "";

        return `<${tag}${attrs}>${children}</${tag}>`;
      }

      function declarationsToCss(declarations = {}) {
        return Object.entries(declarations)
          .filter(([key, value]) => key && value !== null && value !== undefined && value !== "")
          .map(([key, value]) => `  ${key}: ${value};`)
          .join("\n");
      }

      function buildCss() {
        const styles = state.styles || {};
        const variables = styles.variables || {};
        const root = Object.entries(variables)
          .map(([key, value]) => `  ${key}: ${value};`)
          .join("\n");

        const rules = (styles.rules || [])
          .filter(rule => rule.selector)
          .map(rule => `${rule.selector} {\n${declarationsToCss(rule.declarations)}\n}`)
          .join("\n\n");

        const media = (styles.mediaQueries || [])
          .filter(group => group.query)
          .map(group => {
            const nestedRules = (group.rules || [])
              .filter(rule => rule.selector)
              .map(rule => `  ${rule.selector} {\n${declarationsToCss(rule.declarations).split("\n").map(line => "  " + line).join("\n")}\n  }`)
              .join("\n\n");
            return `@media ${group.query} {\n${nestedRules}\n}`;
          })
          .join("\n\n");

        const keyframes = (styles.keyframes || [])
          .filter(frame => frame.name && frame.steps)
          .map(frame => {
            const steps = Object.entries(frame.steps)
              .map(([step, declarations]) => `  ${step} {\n${declarationsToCss(declarations).split("\n").map(line => "  " + line).join("\n")}\n  }`)
              .join("\n");
            return `@keyframes ${frame.name} {\n${steps}\n}`;
          })
          .join("\n\n");

        return `:root {\n${root}\n}\n\n${rules}\n\n${media}\n\n${keyframes}`.trim();
      }

      function buildBodyHtml({ editorMode = true } = {}) {
        return (state.document?.body?.children || [])
          .map((node, index) => renderNode(node, [index], editorMode))
          .join("\n");
      }

      function buildHtmlDocument({ editorMode = true } = {}) {
        const doc = state.document || {};
        const head = doc.head || {};
        const htmlAttributes = attributesToString(doc.htmlAttributes || {});
        const metas = (head.metas || []).map(meta => `<meta${attributesToString(meta)}>`).join("\n");
        const links = (head.links || []).map(link => `<link${attributesToString(link)}>`).join("\n");
        const bodyAttrs = attributesToString(doc.body?.attributes || {});
        const body = buildBodyHtml({ editorMode });

        return `<!DOCTYPE ${doc.doctype || "html"}>
<html${htmlAttributes}>
<head>
<meta charset="UTF-8">
${metas}
<title>${escapeHtml(head.title || "Página")}</title>
${links}
<link rel="stylesheet" href="/static/editor/tailwind.css">
<style data-vjpb-page-style="true">
${buildCss()}
</style>
</head>
<body${bodyAttrs}>
${body}
</body>
</html>`;
      }

      function parsePreviewPath(pathValue) {
        if (typeof pathValue !== "string" || pathValue.trim() === "") return null;

        const path = pathValue
          .split(".")
          .map(part => Number.parseInt(part, 10));

        return path.every(Number.isInteger) ? path : null;
      }

      function highlightSelectedPreviewElement(previewDocument) {
        previewDocument
          .querySelectorAll(".__vjpb-selected")
          .forEach(element => element.classList.remove("__vjpb-selected"));

        if (!Array.isArray(selectedPath)) return;

        const selector = `[data-vjpb-path="${selectedPath.join(".")}"]`;
        const selectedElement = previewDocument.querySelector(selector);

        if (selectedElement) {
          selectedElement.classList.add("__vjpb-selected");
        }

        previewDocument.dispatchEvent(
          new CustomEvent("vjpb:selection-change", { detail: { path: selectedPath } })
        );
      }

      function focusSelectedTreeRow() {
        if (!Array.isArray(selectedPath)) return;

        requestAnimationFrame(() => {
          const treeRow = els.tree.querySelector(
            `[data-tree-path="${selectedPath.join(".")}"]`
          );

          treeRow?.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
        });
      }

      function selectPreviewElement(element) {
        const path = parsePreviewPath(element?.getAttribute("data-vjpb-path"));
        if (!path) return;

        selectedPath = path;
        setActiveTab("structure");
        renderTree();
        renderInspector();
        syncJsonEditor();
        focusSelectedTreeRow();

        const previewDocument = els.previewFrame.contentDocument;
        if (previewDocument) {
          highlightSelectedPreviewElement(previewDocument);
        }

        showToast(`Editando <${element.tagName.toLowerCase()}>`);
      }

      function clearPreviewDropIndicators() {
        if (activePreviewDropElement) {
          activePreviewDropElement.classList.remove(
            "__vjpb-drop-before",
            "__vjpb-drop-inside",
            "__vjpb-drop-after"
          );
        }

        activePreviewDropElement = null;
        activePreviewDropPosition = null;
        activePreviewDropPath = null;
      }

      function canReceivePreviewChildren(node) {
        if (!node || node.type !== "element") return false;

        return new Set([
          "div",
          "section",
          "main",
          "header",
          "footer",
          "nav",
          "article",
          "aside",
          "ul",
          "ol",
          "li",
          "form",
          "figure",
          "figcaption"
        ]).has(String(node.tag || "").toLowerCase());
      }

      function getPreviewDropPosition(element, event, targetNode) {
        const rect = element.getBoundingClientRect();
        const relativeY = event.clientY - rect.top;
        const ratio = rect.height ? relativeY / rect.height : .5;

        // The central nesting area is intentionally small. Most movements
        // therefore behave as normal reordering and accidental nesting is
        // much less likely.
        if (ratio < .38) return "before";
        if (ratio > .62) return "after";

        if (!canReceivePreviewChildren(targetNode)) {
          return ratio < .5 ? "before" : "after";
        }

        return "inside";
      }

      function movePreviewElementInDom(targetElement, position) {
        if (
          !previewDraggedElement ||
          !targetElement ||
          targetElement === previewDraggedElement ||
          previewDraggedElement.contains(targetElement)
        ) {
          return false;
        }

        if (position === "inside") {
          if (targetElement.lastElementChild === previewDraggedElement) {
            return false;
          }

          targetElement.appendChild(previewDraggedElement);
          return true;
        }

        const parent = targetElement.parentNode;
        if (!parent) return false;

        const reference =
          position === "before"
            ? targetElement
            : targetElement.nextSibling;

        if (reference === previewDraggedElement) {
          return false;
        }

        if (
          position === "after" &&
          targetElement.nextSibling === previewDraggedElement
        ) {
          return false;
        }

        parent.insertBefore(previewDraggedElement, reference);
        return true;
      }

      function resetPreviewDrag({ restore = false } = {}) {
        previewDraggedElement?.classList.remove("__vjpb-dragging");
        clearPreviewDropIndicators();

        draggedPreviewPath = null;
        previewDraggedElement = null;
        previewDropCommitted = false;

        if (restore) {
          // Rebuild from state only when a drag was cancelled. A successful
          // drop already updates state and performs its own smooth refresh.
          renderPreview({ immediate: true });
        }
      }

      function installPreviewInteractionHandler() {
        const previewDocument = els.previewFrame.contentDocument;
        if (!previewDocument) return;

        const interactionStyle = previewDocument.createElement("style");
        interactionStyle.dataset.vjpbEditorStyle = "true";
        interactionStyle.textContent = `
          /* Reserve room above the document for the selection outline/shadow
             on top-level nodes — otherwise it paints above y=0 and the
             iframe clips it (editor-only spacing, never exported). */
          body {
            margin-top: 16px !important;
          }

          [data-vjpb-path] {
            cursor: grab !important;
          }

          [data-vjpb-path]:active {
            cursor: grabbing !important;
          }

          [data-vjpb-path].__vjpb-hover {
            outline: 2px dashed #7c7df0 !important;
            outline-offset: 3px !important;
          }

          [data-vjpb-path].__vjpb-selected {
            outline: 3px solid #5b5ce2 !important;
            outline-offset: 4px !important;
            box-shadow: 0 0 0 7px rgba(91, 92, 226, .14) !important;
          }

          [data-vjpb-path].__vjpb-dragging {
            opacity: .34 !important;
            pointer-events: none !important;
            outline: 3px dashed #5b5ce2 !important;
            outline-offset: 4px !important;
            box-shadow: 0 0 0 7px rgba(91, 92, 226, .12) !important;
            filter: saturate(.65) !important;
          }

          [data-vjpb-path].__vjpb-drop-inside {
            outline: 4px solid #5b5ce2 !important;
            outline-offset: 5px !important;
            box-shadow:
              0 0 0 9px rgba(91, 92, 226, .18),
              inset 0 0 0 9999px rgba(91, 92, 226, .05) !important;
          }

          [data-vjpb-path].__vjpb-drop-before,
          [data-vjpb-path].__vjpb-drop-after {
            position: relative !important;
          }

          [data-vjpb-path].__vjpb-drop-before::before,
          [data-vjpb-path].__vjpb-drop-after::after {
            content: "" !important;
            position: absolute !important;
            left: 0 !important;
            right: 0 !important;
            height: 5px !important;
            z-index: 2147483647 !important;
            border-radius: 999px !important;
            background: #5b5ce2 !important;
            box-shadow: 0 0 0 4px rgba(91, 92, 226, .2) !important;
            pointer-events: none !important;
          }

          [data-vjpb-path].__vjpb-drop-before::before {
            top: -7px !important;
          }

          [data-vjpb-path].__vjpb-drop-after::after {
            bottom: -7px !important;
          }
        `;
        previewDocument.head.appendChild(interactionStyle);

        previewDocument
          .querySelectorAll("[data-vjpb-path]")
          .forEach(element => {
            element.draggable = true;
          });

        previewDocument.addEventListener(
          "keydown",
          event => {
            const modifier = event.ctrlKey || event.metaKey;
            if (!modifier) return;

            const key = event.key.toLowerCase();

            if (key === "z" && event.shiftKey) {
              event.preventDefault();
              event.stopPropagation();
              redoChange();
              return;
            }

            if (key === "z") {
              event.preventDefault();
              event.stopPropagation();
              undoChange();
              return;
            }

            if (key === "y") {
              event.preventDefault();
              event.stopPropagation();
              redoChange();
              return;
            }

            if (key === "s") {
              event.preventDefault();
              event.stopPropagation();
              downloadFile(
                "page-template.json",
                JSON.stringify(state, null, 2),
                "application/json"
              );
              showToast("JSON descargado.");
            }
          },
          true
        );

        previewDocument.addEventListener(
          "mouseover",
          event => {
            const target = event.target;
            const editable =
              target && typeof target.closest === "function"
                ? target.closest("[data-vjpb-path]")
                : null;

            if (!editable || editable.classList.contains("__vjpb-selected")) return;
            editable.classList.add("__vjpb-hover");
          },
          true
        );

        previewDocument.addEventListener(
          "mouseout",
          event => {
            const target = event.target;
            const editable =
              target && typeof target.closest === "function"
                ? target.closest("[data-vjpb-path]")
                : null;

            editable?.classList.remove("__vjpb-hover");
          },
          true
        );

        previewDocument.addEventListener(
          "dragstart",
          event => {
            const target = event.target;
            const editable =
              target && typeof target.closest === "function"
                ? target.closest("[data-vjpb-path]")
                : null;

            if (!editable) return;

            const path = parsePreviewPath(
              editable.getAttribute("data-vjpb-path")
            );

            if (!path) return;

            flushHistoryCommit();

            draggedPreviewPath = path;
            selectedPath = [...path];
            previewDraggedElement = editable;
            previewDropCommitted = false;

            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData(
              "text/plain",
              path.join(".")
            );

            // Let the browser capture its normal drag image first. Afterwards
            // the real element becomes a translucent live slot that can move
            // through the layout and push its siblings naturally.
            requestAnimationFrame(() => {
              editable.classList.add("__vjpb-dragging");
            });
          },
          true
        );

        previewDocument.addEventListener(
          "dragover",
          event => {
            if (!draggedPreviewPath || !previewDraggedElement) return;

            const target = event.target;
            const editable =
              target && typeof target.closest === "function"
                ? target.closest("[data-vjpb-path]")
                : null;

            if (
              !editable ||
              editable === previewDraggedElement ||
              previewDraggedElement.contains(editable)
            ) {
              return;
            }

            const targetPath = parsePreviewPath(
              editable.getAttribute("data-vjpb-path")
            );

            if (!targetPath) return;

            const targetNode = getNode(targetPath);
            const position = getPreviewDropPosition(
              editable,
              event,
              targetNode
            );

            const destinationParentPath =
              position === "inside"
                ? targetPath
                : targetPath.slice(0, -1);

            // Never allow a node to become a child of itself or one of its
            // descendants.
            if (
              isPathPrefix(
                draggedPreviewPath,
                destinationParentPath
              )
            ) {
              return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.dataTransfer.dropEffect = "move";

            const destinationChanged =
              activePreviewDropElement !== editable ||
              activePreviewDropPosition !== position ||
              !pathsEqual(activePreviewDropPath, targetPath);

            if (destinationChanged) {
              clearPreviewDropIndicators();

              activePreviewDropElement = editable;
              activePreviewDropPosition = position;
              activePreviewDropPath = [...targetPath];

              // Only nesting needs an explicit target highlight. For sibling
              // reordering, the translucent element itself occupies the real
              // destination and creates the visible space.
              if (position === "inside") {
                editable.classList.add("__vjpb-drop-inside");
              }

              movePreviewElementInDom(editable, position);
            }

            const previewWindow = previewDocument.defaultView;
            const edgeSize = 55;

            if (event.clientY < edgeSize) {
              previewWindow?.scrollBy(0, -14);
            } else if (
              event.clientY >
              previewDocument.documentElement.clientHeight - edgeSize
            ) {
              previewWindow?.scrollBy(0, 14);
            }
          },
          true
        );

        previewDocument.addEventListener(
          "drop",
          event => {
            if (!draggedPreviewPath) return;

            event.preventDefault();
            event.stopPropagation();

            const sourcePath = [...draggedPreviewPath];
            const targetPath = activePreviewDropPath
              ? [...activePreviewDropPath]
              : null;
            const position = activePreviewDropPosition;

            if (!targetPath || !position) {
              resetPreviewDrag({ restore: true });
              return;
            }

            previewDropCommitted = true;

            const moved = moveTreeNode(
              sourcePath,
              targetPath,
              position
            );

            if (!moved) {
              resetPreviewDrag({ restore: true });
              return;
            }

            // The state update is now authoritative. Keep the already-reflowed
            // preview visible until the normal in-place refresh finishes.
            previewDraggedElement?.classList.remove(
              "__vjpb-dragging"
            );
            clearPreviewDropIndicators();

            draggedPreviewPath = null;
            previewDraggedElement = null;

            window.focus();
            els.undoButton.focus({ preventScroll: true });
          },
          true
        );

        previewDocument.addEventListener(
          "dragend",
          () => {
            if (previewDropCommitted) {
              previewDropCommitted = false;
              clearPreviewDropIndicators();
              return;
            }

            // Dropping outside a valid destination restores the preview from
            // the unchanged JSON state.
            if (draggedPreviewPath || previewDraggedElement) {
              resetPreviewDrag({ restore: true });
            }
          },
          true
        );

        previewDocument.addEventListener(
          "click",
          event => {
            const target = event.target;
            const editable =
              target && typeof target.closest === "function"
                ? target.closest("[data-vjpb-path]")
                : null;

            if (!editable) return;

            // The preview works as a visual editor. Prevent buttons, links and
            // form controls from navigating or submitting while selecting.
            event.preventDefault();
            event.stopPropagation();

            selectPreviewElement(editable);
          },
          true
        );

        previewDocument.addEventListener(
          "dblclick",
          event => {
            const target = event.target;
            const editable =
              target && typeof target.closest === "function"
                ? target.closest("[data-vjpb-path]")
                : null;

            if (!editable) return;

            event.preventDefault();
            event.stopPropagation();

            const path = parsePreviewPath(editable.getAttribute("data-vjpb-path"));
            if (!path) return;

            if (editable.tagName.toLowerCase() === "img") {
              openImagePickerModal(path);
              return;
            }
            const tag = editable.tagName.toLowerCase();
            if (tag === "button" || tag === "a") {
              openCtaLinkPrompt(path);
            }
          },
          true
        );

        highlightSelectedPreviewElement(previewDocument);
      }

      function normalizeDomAttributeValue(name, value) {
        if (name === "class" && Array.isArray(value)) {
          return value.filter(Boolean).join(" ");
        }

        if (value === true) return "";
        return String(value);
      }

      function syncDomAttributes(element, attributes = {}) {
        const normalized = new Map();

        for (const [rawName, rawValue] of Object.entries(attributes)) {
          const name = String(rawName).trim();

          if (
            !name ||
            name.toLowerCase().startsWith("on") ||
            rawValue === null ||
            rawValue === undefined ||
            rawValue === false ||
            rawValue === ""
          ) {
            continue;
          }

          normalized.set(name, normalizeDomAttributeValue(name, rawValue));
        }

        [...element.attributes].forEach(attribute => {
          if (
            !normalized.has(attribute.name) &&
            !attribute.name.startsWith("data-vjpb-")
          ) {
            element.removeAttribute(attribute.name);
          }
        });

        normalized.forEach((value, name) => {
          element.setAttribute(name, value);
        });
      }

      function capturePreviewScroll() {
        const previewWindow = els.previewFrame.contentWindow;

        return {
          x: previewWindow?.scrollX || 0,
          y: previewWindow?.scrollY || 0
        };
      }

      function restorePreviewScroll(position) {
        const previewWindow = els.previewFrame.contentWindow;
        if (!previewWindow) return;

        requestAnimationFrame(() => {
          previewWindow.scrollTo(position.x, position.y);
        });
      }

      function updatePreviewInPlace() {
        const previewDocument = els.previewFrame.contentDocument;

        if (
          previewDraggedElement &&
          !previewDropCommitted
        ) {
          previewDraggedElement.classList.remove(
            "__vjpb-dragging"
          );
          draggedPreviewPath = null;
          previewDraggedElement = null;
          clearPreviewDropIndicators();
        }

        if (!previewReady || !previewDocument?.body) {
          loadPreviewDocument();
          return;
        }

        const scrollPosition = capturePreviewScroll();
        const doc = state.document || {};
        const head = doc.head || {};

        previewDocument.title = head.title || "Página";
        syncDomAttributes(
          previewDocument.documentElement,
          doc.htmlAttributes || {}
        );
        syncDomAttributes(
          previewDocument.body,
          doc.body?.attributes || {}
        );

        let pageStyle = previewDocument.querySelector(
          "style[data-vjpb-page-style]"
        );

        if (!pageStyle) {
          pageStyle = previewDocument.createElement("style");
          pageStyle.dataset.vjpbPageStyle = "true";
          previewDocument.head.prepend(pageStyle);
        }

        // Update CSS and page markup without reloading the iframe. This keeps
        // the viewport stable and removes the white flash between keystrokes.
        pageStyle.textContent = buildCss();
        previewDocument.body.innerHTML = buildBodyHtml({
          editorMode: true
        });

        previewDocument
          .querySelectorAll("[data-vjpb-path]")
          .forEach(element => {
            element.draggable = true;
          });

        highlightSelectedPreviewElement(previewDocument);
        restorePreviewScroll(scrollPosition);
      }

      function loadPreviewDocument() {
        clearTimeout(previewUpdateTimer);

        const scrollPosition = capturePreviewScroll();
        const loadToken = ++previewLoadToken;
        previewReady = false;

        els.previewFrame.onload = () => {
          if (loadToken !== previewLoadToken) return;

          previewReady = true;
          installPreviewInteractionHandler();
          restorePreviewScroll(scrollPosition);
        };

        els.previewFrame.srcdoc = buildHtmlDocument();
      }

      function renderPreview({ full = false, immediate = false } = {}) {
        clearTimeout(previewUpdateTimer);

        if (
          full ||
          !previewReady ||
          !els.previewFrame.contentDocument?.body
        ) {
          loadPreviewDocument();
          return;
        }

        if (immediate) {
          updatePreviewInPlace();
          return;
        }

        // A small debounce groups rapid keystrokes into one visual update.
        previewUpdateTimer = setTimeout(updatePreviewInPlace, 75);
      }

      function syncJsonEditor() {
        els.jsonEditor.value = JSON.stringify(state, null, 2);
        els.jsonError.classList.remove("visible");
      }

      function updateAll({
        keepJsonText = false,
        fullPreview = false,
        skipHistory = false
      } = {}) {
        renderPreview({ full: fullPreview });
        renderTree();
        renderInspector();
        syncGeneralForms();
        if (!keepJsonText) syncJsonEditor();

        if (!skipHistory) {
          scheduleHistoryCommit();
        }
      }

      function setActiveTab(name) {
        els.tabs.forEach(tab => {
          const active = tab.dataset.tab === name;
          tab.classList.toggle("active", active);
          tab.setAttribute("aria-selected", String(active));
        });
        els.panels.forEach(panel => {
          const active = panel.dataset.panel === name;
          panel.classList.toggle("active", active);
          panel.setAttribute("aria-hidden", String(!active));
        });
      }

      els.tabs.forEach(tab => {
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", String(tab.classList.contains("active")));
        tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
      });
      els.panels.forEach(panel => {
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-hidden", String(!panel.classList.contains("active")));
      });
      setActiveTab(els.tabs.find(tab => tab.classList.contains("active"))?.dataset.tab || "content");

      document.querySelectorAll(".device-button").forEach(button => {
        button.addEventListener("click", () => {
          document.querySelectorAll(".device-button").forEach(item => {
            const active = item === button;
            item.classList.toggle("active", active);
            item.setAttribute("aria-pressed", String(active));
          });
          els.previewWrap.className = "preview-frame-wrap";
          if (button.dataset.device !== "desktop") {
            els.previewWrap.classList.add(button.dataset.device);
          }
        });
      });

      function findNodes(predicate, nodes = state.document.body.children, path = []) {
        const found = [];
        nodes.forEach((node, index) => {
          const currentPath = [...path, index];
          if (predicate(node)) found.push({ node, path: currentPath });
          if (node.type === "element" && Array.isArray(node.children)) {
            found.push(...findNodes(predicate, node.children, currentPath));
          }
        });
        return found;
      }

      function findFirstElement(tag, className) {
        const result = findNodes(node => {
          if (node.type !== "element") return false;
          if (tag && node.tag !== tag) return false;
          if (!className) return true;
          return Array.isArray(node.attributes?.class) && node.attributes.class.includes(className);
        });
        return result[0]?.node || null;
      }

      function firstTextNode(node) {
        if (!node || !Array.isArray(node.children)) return null;
        for (const child of node.children) {
          if (child.type === "text") return child;
          if (child.type === "element") {
            const nested = firstTextNode(child);
            if (nested) return nested;
          }
        }
        return null;
      }

      function syncGeneralForms() {
        ensureStyleShape(state);
        const heroTitle = findFirstElement("h1", null);
        const heroDescription = findFirstElement("p", "hero-description");
        const vars = state.styles.variables;

        document.getElementById("quickTitle").value = state.document.head.title || "";
        document.getElementById("quickHeroTitle").value = firstTextNode(heroTitle)?.value || "";
        document.getElementById("quickHeroDescription").value = firstTextNode(heroDescription)?.value || "";

        setColorPair("primaryColor", "primaryColorPicker", vars["--color-primary"] || "#5b5ce2");
        setColorPair("backgroundColor", "backgroundColorPicker", vars["--color-background"] || "#ffffff");
        setColorPair("textColor", "textColorPicker", vars["--color-text"] || "#111827");
        setColorPair("surfaceColor", "surfaceColorPicker", vars["--color-surface"] || "#ffffff");

        document.getElementById("fontFamily").value = vars["--font-primary"] || "Inter, Arial, sans-serif";
        document.getElementById("maxWidth").value = vars["--max-width"] || "";
        document.getElementById("borderRadius").value = vars["--radius"] || "";
        document.getElementById("sectionSpacing").value = vars["--section-spacing"] || "";

        document.getElementById("documentLanguage").value = state.document.htmlAttributes.lang || "es";
        document.getElementById("documentDirection").value = state.document.htmlAttributes.dir || "ltr";
        document.getElementById("seoTitle").value = state.document.head.title || "";
        document.getElementById("seoDescription").value = getMeta("description")?.content || "";
        document.getElementById("canonicalUrl").value = getCanonicalLink()?.href || "";
        renderPaletteControls();
      }

      function setColorPair(textId, pickerId, value) {
        document.getElementById(textId).value = value;
        if (/^#[0-9a-f]{6}$/i.test(value)) {
          document.getElementById(pickerId).value = value;
        }
      }

      function bindInput(id, handler, eventName = "input") {
        document.getElementById(id).addEventListener(eventName, event => {
          if (handler(event.target.value) !== false) updateAll();
        });
      }

      bindInput("quickTitle", value => state.document.head.title = value);
      bindInput("quickHeroTitle", value => {
        const node = findFirstElement("h1", null);
        const text = firstTextNode(node);
        if (text) text.value = value;
      });
      bindInput("quickHeroDescription", value => {
        const node = findFirstElement("p", "hero-description");
        const text = firstTextNode(node);
        if (text) text.value = value;
      });

      [
        ["primaryColor", "primaryColorPicker", "--color-primary"],
        ["backgroundColor", "backgroundColorPicker", "--color-background"],
        ["textColor", "textColorPicker", "--color-text"],
        ["surfaceColor", "surfaceColorPicker", "--color-surface"]
      ].forEach(([textId, pickerId, variable]) => {
        bindInput(textId, value => {
          const normalized = value.trim();
          if (!isHexColor(normalized)) {
            setPaletteFeedback("Usá un color HEX de seis dígitos, por ejemplo #2563EB.", "error");
            return false;
          }
          ensureStyleShape(state);
          state.styles.variables[variable] = normalized;
          markPaletteCustom();
          return true;
        });
        bindInput(pickerId, value => {
          ensureStyleShape(state);
          state.styles.variables[variable] = value;
          markPaletteCustom();
        });
      });

      populatePaletteSelect();
      document.getElementById("palettePresetSelect")?.addEventListener("change", event => {
        const value = event.target.value;
        if (value === "custom") {
          flushHistoryCommit();
          markPaletteCustom();
          updateAll({ skipHistory: true });
          commitHistorySnapshot();
          showToast("Paleta personalizada lista.", "success");
        } else if (value !== "ai") {
          applyPalette(value);
        }
      });
      bindInput("paletteName", value => {
        markPaletteCustom(value);
      });
      document.getElementById("paletteSaveButton")?.addEventListener("click", saveUserPalette);
      document.getElementById("paletteDeleteButton")?.addEventListener("click", deleteUserPalette);
      document.getElementById("paletteResetButton")?.addEventListener("click", resetPalette);

      bindInput("fontFamily", value => state.styles.variables["--font-primary"] = value, "change");
      bindInput("maxWidth", value => state.styles.variables["--max-width"] = value);
      bindInput("borderRadius", value => state.styles.variables["--radius"] = value);
      bindInput("sectionSpacing", value => state.styles.variables["--section-spacing"] = value);
      bindInput("documentLanguage", value => state.document.htmlAttributes.lang = value, "change");
      bindInput("documentDirection", value => state.document.htmlAttributes.dir = value, "change");
      bindInput("seoTitle", value => state.document.head.title = value);
      bindInput("seoDescription", value => ensureMeta("description").content = value);
      bindInput("canonicalUrl", value => ensureCanonicalLink().href = value);

      function getNode(path) {
        if (!Array.isArray(path)) return null;
        let children = state.document.body.children;
        let node = null;
        for (const index of path) {
          node = children[index];
          if (!node) return null;
          children = node.children || [];
        }
        return node;
      }

      function getParentInfo(path) {
        if (!Array.isArray(path) || path.length === 0) return null;
        const parentPath = path.slice(0, -1);
        const index = path[path.length - 1];
        const parentNode = parentPath.length ? getNode(parentPath) : null;
        const children = parentNode ? parentNode.children : state.document.body.children;
        return { parentNode, children, index, parentPath };
      }

      function pathsEqual(first, second) {
        return (
          Array.isArray(first) &&
          Array.isArray(second) &&
          first.length === second.length &&
          first.every((value, index) => value === second[index])
        );
      }

      function isPathPrefix(prefix, path) {
        return (
          Array.isArray(prefix) &&
          Array.isArray(path) &&
          prefix.length <= path.length &&
          prefix.every((value, index) => value === path[index])
        );
      }

      function findNodePathByReference(
        reference,
        nodes = state.document.body.children,
        parentPath = []
      ) {
        for (let index = 0; index < nodes.length; index += 1) {
          const node = nodes[index];
          const path = [...parentPath, index];

          if (node === reference) {
            return path;
          }

          if (node?.type === "element" && Array.isArray(node.children)) {
            const nestedPath = findNodePathByReference(
              reference,
              node.children,
              path
            );

            if (nestedPath) return nestedPath;
          }
        }

        return null;
      }

      function canContainChildren(node) {
        if (!node || node.type !== "element") return false;

        const voidTags = new Set([
          "area",
          "base",
          "br",
          "col",
          "embed",
          "hr",
          "img",
          "input",
          "link",
          "meta",
          "param",
          "source",
          "track",
          "wbr"
        ]);

        return !voidTags.has(String(node.tag || "").toLowerCase());
      }

      function clearTreeDropIndicators() {
        if (activeDropRow) {
          activeDropRow.classList.remove(
            "drop-before",
            "drop-inside",
            "drop-after"
          );
        }

        activeDropRow = null;
        activeDropPosition = null;
      }

      function getDropPosition(row, event, targetNode) {
        const rect = row.getBoundingClientRect();
        const relativeY = event.clientY - rect.top;
        const ratio = rect.height ? relativeY / rect.height : .5;

        if (ratio < .28) return "before";
        if (ratio > .72) return "after";

        // Text and void elements cannot receive children. Their center is
        // treated as the closest sibling position instead.
        if (!canContainChildren(targetNode)) {
          return ratio < .5 ? "before" : "after";
        }

        return "inside";
      }

      function moveTreeNode(sourcePath, targetPath, position) {
        if (
          !Array.isArray(sourcePath) ||
          !Array.isArray(targetPath) ||
          !["before", "inside", "after"].includes(position)
        ) {
          return false;
        }

        if (pathsEqual(sourcePath, targetPath)) {
          showToast("El elemento ya está en esa posición.");
          return false;
        }

        const sourceInfo = getParentInfo(sourcePath);
        const sourceNode = getNode(sourcePath);
        const targetInfo = getParentInfo(targetPath);
        const targetNode = getNode(targetPath);

        if (!sourceInfo || !sourceNode || !targetInfo || !targetNode) {
          showToast("No fue posible mover el elemento.");
          return false;
        }

        let destinationChildren;
        let destinationIndex;
        let destinationParentPath;

        if (position === "inside") {
          if (!canContainChildren(targetNode)) {
            showToast("Ese elemento no puede contener otros elementos.");
            return false;
          }

          destinationChildren = targetNode.children ||= [];
          destinationIndex = destinationChildren.length;
          destinationParentPath = targetPath;
        } else {
          destinationChildren = targetInfo.children;
          destinationIndex =
            targetInfo.index + (position === "after" ? 1 : 0);
          destinationParentPath = targetInfo.parentPath;
        }

        // A node cannot be moved inside itself or inside one of its descendants.
        if (isPathPrefix(sourcePath, destinationParentPath)) {
          showToast("No puedes mover un elemento dentro de sí mismo.");
          return false;
        }

        const sourceChildren = sourceInfo.children;
        const sourceIndex = sourceInfo.index;
        const movedNode = sourceChildren[sourceIndex];

        sourceChildren.splice(sourceIndex, 1);

        if (
          sourceChildren === destinationChildren &&
          sourceIndex < destinationIndex
        ) {
          destinationIndex -= 1;
        }

        destinationIndex = Math.max(
          0,
          Math.min(destinationIndex, destinationChildren.length)
        );

        destinationChildren.splice(destinationIndex, 0, movedNode);

        selectedPath = findNodePathByReference(movedNode);
        updateAll();
        flushHistoryCommit();
        focusSelectedTreeRow();

        showToast(
          position === "inside"
            ? "Elemento movido dentro del destino."
            : "Elemento reordenado."
        );

        return true;
      }

      function renderTree() {
        const root = document.createElement("ul");
        root.className = "tree-list";
        state.document.body.children.forEach((node, index) => {
          root.appendChild(createTreeItem(node, [index]));
        });
        els.tree.replaceChildren(root);
      }

      function createTreeItem(node, path) {
        const li = document.createElement("li");
        li.className = "tree-node";

        const row = document.createElement("div");
        row.className = "tree-row";
        row.dataset.treePath = path.join(".");
        row.draggable = true;
        row.tabIndex = 0;
        row.setAttribute("role", "button");

        if (JSON.stringify(path) === JSON.stringify(selectedPath)) {
          row.classList.add("selected");
        }

        const dragHandle = document.createElement("span");
        dragHandle.className = "tree-drag-handle";
        dragHandle.textContent = "•••";
        dragHandle.setAttribute("aria-hidden", "true");

        const tag = document.createElement("span");
        tag.className = "tree-tag";
        tag.textContent = node.type === "text" ? "#text" : `<${node.tag}>`;

        const description = document.createElement("span");
        description.className = "tree-description";
        if (node.type === "text") {
          description.textContent = node.value || "(vacío)";
        } else {
          const id = node.attributes?.id ? `#${node.attributes.id}` : "";
          const classes = Array.isArray(node.attributes?.class) && node.attributes.class.length
            ? "." + node.attributes.class.join(".")
            : "";
          const text = firstTextNode(node)?.value || "";
          description.textContent = `${id}${classes}${text ? " · " + text : ""}`;
        }

        row.append(dragHandle, tag, description);

        row.addEventListener("dragstart", event => {
          // Close any pending text/style edit as its own undoable action
          // before starting the drag operation.
          flushHistoryCommit();

          draggedTreePath = [...path];
          selectedPath = [...path];

          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData(
            "text/plain",
            draggedTreePath.join(".")
          );

          requestAnimationFrame(() => {
            row.classList.add("dragging");
          });
        });

        row.addEventListener("dragover", event => {
          if (!draggedTreePath) return;

          event.preventDefault();
          event.stopPropagation();
          event.dataTransfer.dropEffect = "move";

          const targetNode = getNode(path);
          const position = getDropPosition(row, event, targetNode);

          if (
            activeDropRow !== row ||
            activeDropPosition !== position
          ) {
            clearTreeDropIndicators();
            activeDropRow = row;
            activeDropPosition = position;
            row.classList.add(`drop-${position}`);
          }

          const treeRect = els.tree.getBoundingClientRect();
          const edgeSize = 42;

          if (event.clientY < treeRect.top + edgeSize) {
            els.tree.scrollTop -= 12;
          } else if (event.clientY > treeRect.bottom - edgeSize) {
            els.tree.scrollTop += 12;
          }
        });

        row.addEventListener("dragleave", event => {
          if (
            event.relatedTarget &&
            row.contains(event.relatedTarget)
          ) {
            return;
          }

          if (activeDropRow === row) {
            clearTreeDropIndicators();
          }
        });

        row.addEventListener("drop", event => {
          event.preventDefault();
          event.stopPropagation();

          const transferredPath = event.dataTransfer
            .getData("text/plain")
            .split(".")
            .filter(Boolean)
            .map(value => Number.parseInt(value, 10));

          const sourcePath =
            transferredPath.length &&
            transferredPath.every(Number.isInteger)
              ? transferredPath
              : draggedTreePath;

          const position =
            activeDropRow === row && activeDropPosition
              ? activeDropPosition
              : getDropPosition(row, event, getNode(path));

          clearTreeDropIndicators();

          if (sourcePath) {
            moveTreeNode(sourcePath, path, position);
          }
        });

        row.addEventListener("dragend", () => {
          row.classList.remove("dragging");
          draggedTreePath = null;
          clearTreeDropIndicators();
        });

        const selectTreeRow = () => {
          selectedPath = path;
          renderTree();
          renderInspector();

          const previewDocument = els.previewFrame.contentDocument;
          if (previewDocument) {
            highlightSelectedPreviewElement(previewDocument);

            const selectedElement = previewDocument.querySelector(
              `[data-vjpb-path="${selectedPath.join(".")}"]`
            );

            selectedElement?.scrollIntoView({
              behavior: "smooth",
              block: "center"
            });
          }
        };

        row.addEventListener("click", selectTreeRow);

        row.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectTreeRow();
          }
        });
        li.appendChild(row);

        if (node.type === "element" && Array.isArray(node.children) && node.children.length) {
          const childList = document.createElement("ul");
          childList.className = "tree-list";
          node.children.forEach((child, index) => childList.appendChild(createTreeItem(child, [...path, index])));
          li.appendChild(childList);
        }

        return li;
      }

      function normalizeClasses(value) {
        return value.split(/\s+/).map(item => item.trim()).filter(Boolean);
      }

      // --- Tailwind utility-class quick-style controls --------------------
      // Replaces the old setInlineStyleProperty-based "Estilo rápido" panel:
      // instead of an inline style="" attribute, each control adds/removes a
      // Tailwind class token on attributes.class, one family at a time (the
      // matcher identifies every existing token from that same family so a
      // new pick replaces the old one instead of stacking both).
      const UTILITY_FAMILY_MATCHERS = {
        bg: c => /^bg-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d+$/.test(c)
          || /^bg-\[var\(/.test(c) || c === "bg-white" || c === "bg-black" || c === "bg-transparent",
        text_color: c => /^text-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d+$/.test(c)
          || /^text-\[var\(/.test(c) || c === "text-white" || c === "text-black",
        padding: c => /^p-/.test(c),
        margin: c => /^m-/.test(c),
        width: c => /^w-/.test(c),
        text_align: c => ["text-left", "text-center", "text-right", "text-justify"].includes(c),
      };

      function getClassList(node) {
        const attrs = node.attributes || {};
        if (Array.isArray(attrs.class)) return [...attrs.class];
        return attrs.class ? attrs.class.split(/\s+/).filter(Boolean) : [];
      }

      function setClassList(node, classes) {
        node.attributes ||= {};
        if (classes.length) node.attributes.class = classes;
        else delete node.attributes.class;
      }

      function firstMatchingClass(node, family) {
        return getClassList(node).find(UTILITY_FAMILY_MATCHERS[family]) || "";
      }

      function setUtilityClass(node, family, newToken) {
        const classes = getClassList(node).filter(c => !UTILITY_FAMILY_MATCHERS[family](c));
        if (newToken) classes.push(newToken);
        setClassList(node, classes);
      }

      // Small curated pick-lists for the quick-style dropdowns — not every
      // Tailwind value, just common ones. The free-text "Clases CSS" field
      // covers anything else.
      const TAILWIND_QUICK_BG_OPTIONS = [
        ["", "Ninguno"],
        ["bg-[var(--color-primary)]", "Color principal"],
        ["bg-white", "Blanco"],
        ["bg-slate-100", "Gris claro"],
        ["bg-slate-900", "Gris oscuro"],
        ["bg-blue-500", "Azul"],
        ["bg-emerald-500", "Verde"],
        ["bg-amber-500", "Amarillo"],
        ["bg-red-500", "Rojo"],
      ];
      const TAILWIND_QUICK_TEXT_COLOR_OPTIONS = [
        ["", "Ninguno"],
        ["text-[var(--color-primary)]", "Color principal"],
        ["text-white", "Blanco"],
        ["text-slate-900", "Gris oscuro"],
        ["text-slate-500", "Gris medio"],
        ["text-blue-500", "Azul"],
        ["text-red-500", "Rojo"],
      ];
      const TAILWIND_QUICK_SPACING_SCALE = ["", "2", "4", "6", "8", "12", "16", "24"];
      const TAILWIND_QUICK_WIDTH_OPTIONS = [
        ["", "Predeterminado"],
        ["w-full", "Completo (100%)"],
        ["w-1/2", "Mitad (50%)"],
        ["w-1/3", "Un tercio"],
        ["w-2/3", "Dos tercios"],
        ["w-auto", "Automático"],
      ];

      function renderInspector() {
        const node = getNode(selectedPath);
        if (!node) {
          els.inspector.innerHTML = '<div class="inspector-empty">Selecciona un elemento para editarlo.</div>';
          return;
        }

        if (node.type === "text") {
          els.inspector.innerHTML = `
            <div class="section-card">
              <h3>Editar texto</h3>
              <label class="field">
                <span>Contenido</span>
                <textarea class="control" id="nodeTextValue"></textarea>
              </label>
            </div>
          `;
          const input = document.getElementById("nodeTextValue");
          input.value = node.value || "";
          input.addEventListener("input", event => {
            node.value = event.target.value;
            renderPreview();
            renderTree();
            syncJsonEditor();
            scheduleHistoryCommit();
          });
          return;
        }

        const attrs = node.attributes || {};
        const classes = Array.isArray(attrs.class) ? attrs.class.join(" ") : (attrs.class || "");
        const text = firstTextNode(node)?.value || "";

        els.inspector.innerHTML = `
          <div class="section-card">
            <h3>Elemento seleccionado</h3>
            <div class="form-grid two">
              <label class="field">
                <span>Etiqueta HTML</span>
                <select class="control" id="nodeTag">
                  ${["section","div","header","main","footer","nav","article","aside","h1","h2","h3","p","span","a","button","img","ul","li"].map(tag => `<option value="${tag}">${tag}</option>`).join("")}
                </select>
              </label>
              <label class="field">
                <span>ID</span>
                <input class="control" id="nodeId" type="text">
              </label>
            </div>

            <label class="field" style="margin-top:12px">
              <span>Clases CSS</span>
              <input class="control" id="nodeClasses" type="text" placeholder="hero container">
              <small>Separa las clases con espacios.</small>
            </label>

            <label class="field" style="margin-top:12px">
              <span>Texto principal</span>
              <textarea class="control" id="nodeText"></textarea>
              <small>Edita el primer nodo de texto que encuentre dentro del elemento.</small>
            </label>

            <div class="form-grid two" style="margin-top:12px">
              <label class="field">
                <span>Enlace href</span>
                <input class="control" id="nodeHref" type="text">
              </label>
              <label class="field">
                <span>Imagen src</span>
                <input class="control" id="nodeSrc" type="text">
              </label>
              <label class="field">
                <span>Texto alternativo</span>
                <input class="control" id="nodeAlt" type="text">
              </label>
              <label class="field">
                <span>Etiqueta accesible</span>
                <input class="control" id="nodeAriaLabel" type="text">
              </label>
            </div>

            <div class="style-fields">
              <h3>Estilo rápido del elemento</h3>
              <p class="panel-help">Clases Tailwind — se agregan/reemplazan en "Clases CSS" de arriba.</p>
              <div class="form-grid two">
                <label class="field">
                  <span>Color de fondo</span>
                  <select class="control" id="nodeBackground">
                    ${TAILWIND_QUICK_BG_OPTIONS.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
                  </select>
                </label>
                <label class="field">
                  <span>Color de texto</span>
                  <select class="control" id="nodeColor">
                    ${TAILWIND_QUICK_TEXT_COLOR_OPTIONS.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
                  </select>
                </label>
                <label class="field">
                  <span>Padding</span>
                  <select class="control" id="nodePadding">
                    ${TAILWIND_QUICK_SPACING_SCALE.map(n => `<option value="${n ? "p-" + n : ""}">${n ? "p-" + n : "Ninguno"}</option>`).join("")}
                  </select>
                </label>
                <label class="field">
                  <span>Margen</span>
                  <select class="control" id="nodeMargin">
                    ${TAILWIND_QUICK_SPACING_SCALE.map(n => `<option value="${n ? "m-" + n : ""}">${n ? "m-" + n : "Ninguno"}</option>`).join("")}
                  </select>
                </label>
                <label class="field">
                  <span>Ancho</span>
                  <select class="control" id="nodeWidth">
                    ${TAILWIND_QUICK_WIDTH_OPTIONS.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
                  </select>
                </label>
                <label class="field">
                  <span>Alineación de texto</span>
                  <select class="control" id="nodeTextAlign">
                    <option value="">Predeterminada</option>
                    <option value="text-left">Izquierda</option>
                    <option value="text-center">Centro</option>
                    <option value="text-right">Derecha</option>
                  </select>
                </label>
              </div>
            </div>
          </div>
        `;

        document.getElementById("nodeTag").value = node.tag || "div";
        document.getElementById("nodeId").value = attrs.id || "";
        document.getElementById("nodeClasses").value = classes;
        document.getElementById("nodeText").value = text;
        document.getElementById("nodeHref").value = attrs.href || "";
        document.getElementById("nodeSrc").value = attrs.src || "";
        document.getElementById("nodeAlt").value = attrs.alt || "";
        document.getElementById("nodeAriaLabel").value = attrs["aria-label"] || "";
        document.getElementById("nodeBackground").value = firstMatchingClass(node, "bg");
        document.getElementById("nodeColor").value = firstMatchingClass(node, "text_color");
        document.getElementById("nodePadding").value = firstMatchingClass(node, "padding");
        document.getElementById("nodeMargin").value = firstMatchingClass(node, "margin");
        document.getElementById("nodeWidth").value = firstMatchingClass(node, "width");
        document.getElementById("nodeTextAlign").value = firstMatchingClass(node, "text_align");

        function bindInspector(id, callback, eventName = "input") {
          document.getElementById(id).addEventListener(eventName, event => {
            callback(event.target.value);
            renderPreview();
            renderTree();
            syncJsonEditor();
            scheduleHistoryCommit();
          });
        }

        bindInspector("nodeTag", value => node.tag = value, "change");
        bindInspector("nodeId", value => {
          node.attributes ||= {};
          if (value) node.attributes.id = value;
          else delete node.attributes.id;
        });
        bindInspector("nodeClasses", value => {
          node.attributes ||= {};
          const values = normalizeClasses(value);
          if (values.length) node.attributes.class = values;
          else delete node.attributes.class;
        });
        bindInspector("nodeText", value => {
          let textNode = firstTextNode(node);
          if (!textNode) {
            node.children ||= [];
            textNode = { type: "text", value: "" };
            node.children.unshift(textNode);
          }
          textNode.value = value;
        });
        bindInspector("nodeHref", value => setAttribute(node, "href", value));
        bindInspector("nodeSrc", value => setAttribute(node, "src", value));
        bindInspector("nodeAlt", value => setAttribute(node, "alt", value));
        bindInspector("nodeAriaLabel", value => setAttribute(node, "aria-label", value));
        function bindUtilityClass(id, family) {
          bindInspector(id, value => {
            setUtilityClass(node, family, value);
            document.getElementById("nodeClasses").value = getClassList(node).join(" ");
          }, "change");
        }
        bindUtilityClass("nodeBackground", "bg");
        bindUtilityClass("nodeColor", "text_color");
        bindUtilityClass("nodePadding", "padding");
        bindUtilityClass("nodeMargin", "margin");
        bindUtilityClass("nodeWidth", "width");
        bindUtilityClass("nodeTextAlign", "text_align");
      }

      function setAttribute(node, name, value) {
        node.attributes ||= {};
        if (value) node.attributes[name] = value;
        else delete node.attributes[name];
      }

      function createTextElement(tag = "p", text = "Nuevo texto") {
        return {
          type: "element",
          tag,
          attributes: {},
          children: [{ type: "text", value: text }]
        };
      }

      function addChild() {
        const selected = getNode(selectedPath);
        if (!selected || selected.type !== "element") {
          showToast("Selecciona un elemento que pueda contener hijos.");
          return;
        }
        selected.children ||= [];
        selected.children.push(createTextElement());
        selectedPath = [...selectedPath, selected.children.length - 1];
        updateAll();
      }

      function duplicateSelected() {
        const info = getParentInfo(selectedPath);
        if (!info) return showToast("Selecciona un elemento.");
        const node = info.children[info.index];
        info.children.splice(info.index + 1, 0, clone(node));
        selectedPath = [...selectedPath.slice(0, -1), info.index + 1];
        updateAll();
      }

      function deleteSelected() {
        const info = getParentInfo(selectedPath);
        if (!info) return showToast("Selecciona un elemento.");
        info.children.splice(info.index, 1);
        selectedPath = null;
        updateAll();
      }

      function moveSelected(direction) {
        const info = getParentInfo(selectedPath);
        if (!info) return showToast("Selecciona un elemento.");
        const nextIndex = info.index + direction;
        if (nextIndex < 0 || nextIndex >= info.children.length) return;
        [info.children[info.index], info.children[nextIndex]] = [info.children[nextIndex], info.children[info.index]];
        selectedPath = [...selectedPath.slice(0, -1), nextIndex];
        updateAll();
      }

      els.tree.addEventListener("dragover", event => {
        if (!draggedTreePath) return;
        event.preventDefault();
      });

      els.tree.addEventListener("drop", event => {
        // Drops are handled by individual rows. Prevent the browser from
        // opening the dragged text when the pointer lands in an empty gap.
        event.preventDefault();
      });

      document.getElementById("addChildButton").addEventListener("click", addChild);
      document.getElementById("duplicateButton").addEventListener("click", duplicateSelected);
      document.getElementById("deleteButton").addEventListener("click", deleteSelected);
      document.getElementById("moveUpButton").addEventListener("click", () => moveSelected(-1));
      document.getElementById("moveDownButton").addEventListener("click", () => moveSelected(1));

      function sectionPreset(name) {
        const presets = {
          hero: {
            type: "element",
            tag: "section",
            attributes: {
              class: [
                "bg-gray-50",
                "py-16",
                "text-gray-900",
                "md:py-24"
              ]
            },
            children: [
              {
                type: "element",
                tag: "div",
                attributes: {
                  class: [
                    "mx-auto",
                    "grid",
                    "w-full",
                    "max-w-6xl",
                    "gap-10",
                    "px-5",
                    "md:grid-cols-2",
                    "md:items-center",
                    "md:px-8"
                  ]
                },
                children: [
                  {
                    type: "element",
                    tag: "div",
                    attributes: { class: ["max-w-2xl"] },
                    children: [
                      {
                        ...createTextElement("h1", "Un título que capta la atención"),
                        attributes: {
                          class: [
                            "text-4xl",
                            "font-black",
                            "leading-tight",
                            "tracking-tight",
                            "md:text-6xl"
                          ]
                        }
                      },
                      {
                        ...createTextElement(
                          "p",
                          "Explica aquí tu propuesta de valor de forma clara y convincente."
                        ),
                        attributes: {
                          class: [
                            "mt-5",
                            "text-lg",
                            "leading-relaxed",
                            "text-gray-600"
                          ]
                        }
                      },
                      {
                        type: "element",
                        tag: "a",
                        attributes: {
                          class: [
                            "mt-7",
                            "inline-flex",
                            "items-center",
                            "justify-center",
                            "rounded-lg",
                            "bg-indigo-600",
                            "px-5",
                            "py-3",
                            "font-bold",
                            "text-white",
                            "shadow-md",
                            "transition",
                            "hover:opacity-90"
                          ],
                          href: "#"
                        },
                        children: [{ type: "text", value: "Comenzar ahora" }]
                      }
                    ]
                  },
                  {
                    type: "element",
                    tag: "div",
                    attributes: {
                      class: [
                        "min-h-48",
                        "rounded-2xl",
                        "bg-indigo-600",
                        "p-8",
                        "shadow-xl",
                        "md:min-h-64"
                      ]
                    },
                    children: [
                      {
                        type: "element",
                        tag: "div",
                        attributes: {
                          class: [
                            "flex",
                            "h-full",
                            "items-end",
                            "rounded-xl",
                            "bg-indigo-500",
                            "p-6",
                            "text-3xl",
                            "font-black",
                            "text-white"
                          ]
                        },
                        children: [{ type: "text", value: "Tu idea, en vivo" }]
                      }
                    ]
                  }
                ]
              }
            ]
          },
          features: {
            type: "element",
            tag: "section",
            attributes: { class: ["bg-white", "py-16", "md:py-24"] },
            children: [
              {
                type: "element",
                tag: "div",
                attributes: {
                  class: ["mx-auto", "w-full", "max-w-6xl", "px-5", "md:px-8"]
                },
                children: [
                  {
                    ...createTextElement("h2", "Beneficios principales"),
                    attributes: {
                      class: [
                        "mb-8",
                        "text-3xl",
                        "font-black",
                        "tracking-tight",
                        "text-gray-900",
                        "md:text-5xl"
                      ]
                    }
                  },
                  {
                    type: "element",
                    tag: "div",
                    attributes: { class: ["grid", "gap-5", "md:grid-cols-3"] },
                    children: [
                      featureCard("Fácil de usar", "Una experiencia clara para cualquier usuario."),
                      featureCard("Rápido", "Obtén resultados sin procesos innecesarios."),
                      featureCard("Flexible", "Adapta el contenido a tu producto o servicio.")
                    ]
                  }
                ]
              }
            ]
          },
          text: {
            type: "element",
            tag: "section",
            attributes: { class: ["bg-gray-50", "py-16", "md:py-24"] },
            children: [
              {
                type: "element",
                tag: "div",
                attributes: {
                  class: ["mx-auto", "w-full", "max-w-3xl", "px-5", "md:px-8"]
                },
                children: [
                  {
                    ...createTextElement("h2", "Título de la sección"),
                    attributes: {
                      class: ["text-3xl", "font-black", "tracking-tight", "text-gray-900", "md:text-5xl"]
                    }
                  },
                  {
                    ...createTextElement(
                      "p",
                      "Escribe aquí la información que quieres compartir con tus visitantes."
                    ),
                    attributes: {
                      class: [
                        "mt-5",
                        "text-lg",
                        "leading-relaxed",
                        "text-gray-600"
                      ]
                    }
                  }
                ]
              }
            ]
          },
          image: {
            type: "element",
            tag: "section",
            attributes: { class: ["bg-white", "py-16", "md:py-24"] },
            children: [
              {
                type: "element",
                tag: "div",
                attributes: {
                  class: ["mx-auto", "w-full", "max-w-6xl", "px-5", "md:px-8"]
                },
                children: [
                  {
                    type: "element",
                    tag: "img",
                    attributes: {
                      src: "https://images.unsplash.com/photo-1551434678-e076c223a692?auto=format&fit=crop&w=1400&q=80",
                      alt: "Equipo trabajando",
                      class: ["h-auto", "w-full", "rounded-2xl", "object-cover", "shadow-lg"]
                    },
                    children: []
                  }
                ]
              }
            ]
          },
          cta: {
            type: "element",
            tag: "section",
            attributes: { class: ["bg-gray-50", "py-16", "md:py-24"] },
            children: [
              {
                type: "element",
                tag: "div",
                attributes: {
                  class: [
                    "mx-auto",
                    "w-full",
                    "max-w-6xl",
                    "rounded-3xl",
                    "bg-indigo-600",
                    "p-8",
                    "text-center",
                    "text-white",
                    "shadow-xl",
                    "md:p-16"
                  ]
                },
                children: [
                  {
                    ...createTextElement("h2", "¿Listo para comenzar?"),
                    attributes: {
                      class: ["text-3xl", "font-black", "tracking-tight", "md:text-5xl"]
                    }
                  },
                  {
                    ...createTextElement(
                      "p",
                      "Da el siguiente paso y descubre todo lo que podemos ofrecerte."
                    ),
                    attributes: {
                      class: ["mx-auto", "mt-4", "max-w-2xl", "text-lg", "text-indigo-100"]
                    }
                  },
                  {
                    type: "element",
                    tag: "a",
                    attributes: {
                      class: [
                        "mt-7",
                        "inline-flex",
                        "items-center",
                        "justify-center",
                        "rounded-lg",
                        "bg-white",
                        "px-5",
                        "py-3",
                        "font-bold",
                        "text-indigo-700",
                        "shadow-md",
                        "transition",
                        "hover:opacity-90"
                      ],
                      href: "#"
                    },
                    children: [{ type: "text", value: "Comenzar" }]
                  }
                ]
              }
            ]
          },
          footer: {
            type: "element",
            tag: "footer",
            attributes: { class: ["border-t", "border-gray-200", "bg-white", "py-8"] },
            children: [
              {
                type: "element",
                tag: "div",
                attributes: {
                  class: [
                    "mx-auto",
                    "flex",
                    "w-full",
                    "max-w-6xl",
                    "flex-col",
                    "gap-3",
                    "px-5",
                    "text-gray-600",
                    "md:flex-row",
                    "md:items-center",
                    "md:justify-between",
                    "md:px-8"
                  ]
                },
                children: [
                  {
                    ...createTextElement("strong", "Mi marca"),
                    attributes: { class: ["font-black", "text-gray-900"] }
                  },
                  createTextElement("span", "© 2026. Todos los derechos reservados.")
                ]
              }
            ]
          }
        };
        return clone(presets[name]);
      }

      function featureCard(title, description) {
        return {
          type: "element",
          tag: "article",
          attributes: {
            class: [
              "rounded-2xl",
              "border",
              "border-gray-200",
              "bg-white",
              "p-6",
              "shadow-sm"
            ]
          },
          children: [
            {
              type: "element",
              tag: "div",
              attributes: {
                class: [
                  "flex",
                  "h-10",
                  "w-10",
                  "items-center",
                  "justify-center",
                  "rounded-lg",
                  "bg-indigo-600",
                  "font-bold",
                  "text-white"
                ]
              },
              children: [{ type: "text", value: "✦" }]
            },
            {
              ...createTextElement("h3", title),
              attributes: { class: ["mt-5", "text-xl", "font-bold", "text-gray-900"] }
            },
            {
              ...createTextElement("p", description),
              attributes: { class: ["mt-2", "leading-relaxed", "text-gray-600"] }
            }
          ]
        };
      }

      document.querySelectorAll("[data-preset]").forEach(button => {
        button.addEventListener("click", () => {
          const node = sectionPreset(button.dataset.preset);
          state.document.body.children.push(node);
          selectedPath = [state.document.body.children.length - 1];
          updateAll();
          setActiveTab("content");
          showToast("Sección agregada.");
        });
      });

      // --- Double-click shortcut: set a button/anchor's purchase URL -------
      // Sellers paste their own checkout URL (they already own it elsewhere)
      // instead of picking a product from maqueta's own catalog/gateway. Pure
      // logic (button->anchor promotion, prompt-result resolution) lives in
      // cta-link.js so it is testable without a browser; this just wires it
      // to the SAME setAttribute(node,"href",value) primitive the inspector's
      // `nodeHref` field uses, matching this project's confirm()-based idiom
      // for simple native-dialog flows (see resetButton above,
      // save-template.js's deleteRevision).
      function openCtaLinkPrompt(path) {
        const node = getNode(path);
        if (!node) return;
        const current = (node.attributes && node.attributes.href) || "";
        const promptResult = window.prompt("Pegá la URL de compra o destino del botón:", current);
        const resolved = window.EditorCtaLink.resolvePromptedHref(promptResult);
        if (resolved.cancelled) return;
        window.EditorCtaLink.promoteButtonToAnchor(node);
        setAttribute(node, "href", resolved.value);
        updateAll();
        showToast("Enlace actualizado.");
      }

      const imagePickerModal = document.getElementById("imagePickerModal");
      const imagePickerSavedGrid = document.getElementById("imagePickerSavedGrid");
      const imagePickerUploadInput = document.getElementById("imagePickerUploadInput");
      const imagePickerUrlInput = document.getElementById("imagePickerUrlInput");
      const imagePickerUrlConfirmBtn = document.getElementById("imagePickerUrlConfirmBtn");
      let imagePickerTargetPath = null;

      function setImageOnTarget(url) {
        const node = getNode(imagePickerTargetPath);
        if (!node) return;
        node.attributes = node.attributes || {};
        node.attributes.src = url;
        if (window.EditorModals) window.EditorModals.closeAll();
        updateAll();
        showToast("Imagen actualizada.");
      }

      function loadSavedAssetsGrid() {
        if (!imagePickerSavedGrid) return;
        imagePickerSavedGrid.innerHTML = "Cargando…";
        fetch("/api/user-templates/wizard-images/", { credentials: "same-origin" })
          .then(response => (response.ok ? response.json() : []))
          .then(assets => {
            if (!assets.length) {
              imagePickerSavedGrid.innerHTML = "No tenés imágenes guardadas todavía.";
              return;
            }
            imagePickerSavedGrid.innerHTML = "";
            assets.forEach((asset, index) => {
              const thumb = document.createElement("button");
              thumb.type = "button";
              thumb.className = "preset";
              thumb.setAttribute("aria-label", "Usar imagen guardada " + (index + 1));
              const bg = asset.placeholder_color || "transparent";
              thumb.innerHTML = `<img src="${asset.url}" alt="Imagen guardada ${index + 1}" style="width:100%;height:64px;object-fit:cover;border-radius:6px;background-color:${bg};">`;
              thumb.addEventListener("click", () => setImageOnTarget(asset.url));
              imagePickerSavedGrid.appendChild(thumb);
            });
          })
          .catch(() => {
            imagePickerSavedGrid.innerHTML = "No se pudieron cargar tus imágenes.";
          });
      }

      function openImagePickerModal(path) {
        if (!imagePickerModal) return;
        imagePickerTargetPath = path;
        loadSavedAssetsGrid();
        if (window.EditorModals) window.EditorModals.open(imagePickerModal);
      }

      if (imagePickerUploadInput) {
        imagePickerUploadInput.addEventListener("change", () => {
          const file = imagePickerUploadInput.files && imagePickerUploadInput.files[0];
          if (!file) return;
          const body = new FormData();
          body.append("file", file);
          fetch("/api/user-templates/wizard-images/", {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || "" },
            body
          })
            .then(response => (response.ok ? response.json() : Promise.reject()))
            .then(asset => setImageOnTarget(asset.url))
            .catch(() => showToast("No se pudo subir la imagen."))
            .finally(() => { imagePickerUploadInput.value = ""; });
        });
      }

      if (imagePickerUrlConfirmBtn) {
        imagePickerUrlConfirmBtn.addEventListener("click", () => {
          const url = imagePickerUrlInput.value.trim();
          if (!url) {
            showToast("Pegá una URL de imagen.");
            return;
          }
          setImageOnTarget(url);
          imagePickerUrlInput.value = "";
        });
      }

      document.querySelectorAll("[data-image-tab]").forEach(btn => {
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", String(btn.classList.contains("active")));
        btn.addEventListener("click", () => {
          document.querySelectorAll("[data-image-tab]").forEach(b => {
            const active = b === btn;
            b.classList.toggle("active", active);
            b.setAttribute("aria-selected", String(active));
          });
          document.querySelectorAll("[data-image-panel]").forEach(panel => {
            const active = panel.dataset.imagePanel === btn.dataset.imageTab;
            panel.classList.toggle("active", active);
            panel.setAttribute("aria-hidden", String(!active));
          });
        });
      });
      document.querySelectorAll("[data-image-panel]").forEach(panel => {
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-hidden", String(!panel.classList.contains("active")));
      });

      function downloadFile(filename, content, mime) {
        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      }

      document.getElementById("downloadButton").addEventListener("click", () => {
        downloadFile("page-template.json", JSON.stringify(state, null, 2), "application/json");
        showToast("JSON descargado.");
      });

      document.getElementById("downloadHtmlButton").addEventListener("click", () => {
        downloadFile(
          "index.html",
          buildHtmlDocument({ editorMode: false }),
          "text/html"
        );
        showToast("HTML descargado.");
      });

      document.getElementById("copyButton").addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(JSON.stringify(state, null, 2));
          showToast("JSON copiado al portapapeles.");
        } catch {
          showToast("No fue posible copiar automáticamente.");
        }
      });

      els.undoButton.addEventListener("click", undoChange);
      els.redoButton.addEventListener("click", redoChange);

      document.getElementById("importButton").addEventListener("click", () => els.fileInput.click());

      els.fileInput.addEventListener("change", async event => {
        const file = event.target.files?.[0];
        if (!file) return;
        try {
          const parsed = JSON.parse(await file.text());
          validateImportedState(parsed);
          state = ensureStyleShape(parsed);
          paletteBaseline = capturePaletteSnapshot(state);
          selectedPath = null;
          updateAll({ fullPreview: true });
          showToast("JSON importado correctamente.");
        } catch (error) {
          showToast(`No se pudo importar: ${error.message}`);
        } finally {
          event.target.value = "";
        }
      });

      function validateImportedState(value) {
        if (!value || typeof value !== "object") throw new Error("el archivo no contiene un objeto");
        if (!value.document?.body?.children || !Array.isArray(value.document.body.children)) {
          throw new Error("falta document.body.children");
        }
        if (!value.document.head) throw new Error("falta document.head");
        if (!value.styles) value.styles = { variables: {}, rules: [], mediaQueries: [], keyframes: [] };
        if (!value.styles.variables) value.styles.variables = {};
        if (!value.styles.rules) value.styles.rules = [];
      }

      document.getElementById("resetButton").addEventListener("click", () => {
        if (!confirm("¿Quieres reemplazar todos los cambios por el ejemplo inicial?")) return;
        state = clone(defaultPage);
        paletteBaseline = capturePaletteSnapshot(state);
        selectedPath = null;
        updateAll({ fullPreview: true });
        showToast("Ejemplo restablecido.");
      });

      document.getElementById("applyJsonButton").addEventListener("click", () => {
        try {
          const parsed = JSON.parse(els.jsonEditor.value);
          validateImportedState(parsed);
          state = ensureStyleShape(parsed);
          paletteBaseline = capturePaletteSnapshot(state);
          selectedPath = null;
          els.jsonError.classList.remove("visible");
          updateAll({ fullPreview: true });
          showToast("JSON aplicado.");
        } catch (error) {
          els.jsonError.textContent = `JSON inválido: ${error.message}`;
          els.jsonError.classList.add("visible");
        }
      });

      document.getElementById("formatJsonButton").addEventListener("click", () => {
        try {
          els.jsonEditor.value = JSON.stringify(JSON.parse(els.jsonEditor.value), null, 2);
          els.jsonError.classList.remove("visible");
        } catch (error) {
          els.jsonError.textContent = `JSON inválido: ${error.message}`;
          els.jsonError.classList.add("visible");
        }
      });

      document.addEventListener("keydown", event => {
        const modifier = event.ctrlKey || event.metaKey;
        if (!modifier) return;

        const key = event.key.toLowerCase();

        if (key === "s") {
          event.preventDefault();
          downloadFile(
            "page-template.json",
            JSON.stringify(state, null, 2),
            "application/json"
          );
          showToast("JSON descargado.");
          return;
        }

        if (key === "z" && event.shiftKey) {
          event.preventDefault();
          redoChange();
          return;
        }

        if (key === "z") {
          event.preventDefault();
          undoChange();
          return;
        }

        if (key === "y") {
          event.preventDefault();
          redoChange();
        }
      });

      paletteBaseline = capturePaletteSnapshot(state);
      updateHistoryButtons();
      updateAll({ skipHistory: true });

      // --- AI assistant integration facade ----------------------------------
      // Exposes a small, explicit API for editor-ai.js. Everything the AI panel
      // touches goes through here so the core editor stays untouched otherwise.
      window.EditorCore = {
        showToast,
        getState() {
          return clone(state);
        },
        getSelectedPath() {
          return Array.isArray(selectedPath) ? [...selectedPath] : null;
        },
        getSelectedNode() {
          if (!Array.isArray(selectedPath)) return null;
          const node = getNode(selectedPath);
          return node ? clone(node) : null;
        },
        getNodeAt(path) {
          const node = getNode(path);
          return node ? clone(node) : null;
        },
        getDesignVariables() {
          return clone((state.styles && state.styles.variables) || {});
        },
        getPaletteCatalog() {
          return clone(paletteCatalog);
        },
        getPalette() {
          return clone(currentPaletteDescriptor());
        },
        applyPalette,
        getPageSummary() {
          const head = (state.document && state.document.head) || {};
          const htmlAttrs = (state.document && state.document.htmlAttributes) || {};
          return { title: head.title || "", language: htmlAttrs.lang || "es" };
        },
        // Top-level body children with their REAL current index — sent to the
        // AI so path-based ops (delete_node/replace_node especially) target
        // what is actually on the page instead of a guessed/stale layout.
        getBodyOutline() {
          const children = (state.document && state.document.body && state.document.body.children) || [];
          return children.map((node, index) => {
            if (node.type === "text") {
              return { index, type: "text", preview: (node.value || "").slice(0, 40) };
            }
            const cls = node.attributes && node.attributes.class;
            return {
              index,
              tag: node.tag,
              class: Array.isArray(cls) ? cls.join(" ") : cls || "",
            };
          });
        },
        // Commit a proposed state as a SINGLE undo step.
        commitProposal(proposalState) {
          flushHistoryCommit();
          state = ensureStyleShape(proposalState);
          if (Array.isArray(selectedPath) && !getNode(selectedPath)) {
            selectedPath = null;
          }
          updateAll({ skipHistory: true });
          commitHistorySnapshot();
        },
        // Load the server-injected template seed as the initial state.
        // Resets history instead of pushing onto it, so undo can never reach
        // the built-in defaultPage placeholder that state/historyPast boot with.
        loadSeed(proposalState) {
          flushHistoryCommit();
          state = ensureStyleShape(proposalState);
          paletteBaseline = capturePaletteSnapshot(state);
          if (Array.isArray(selectedPath) && !getNode(selectedPath)) {
            selectedPath = null;
          }
          updateAll({ skipHistory: true });
          historyPast = [JSON.stringify(state)];
          historyFuture = [];
          updateHistoryButtons();
        },
        // Deselect the current element (click-outside handling lives in
        // editor-ai.js, since selectedPath is private to this closure).
        clearSelection() {
          if (selectedPath === null) return;
          selectedPath = null;
          updateAll({ skipHistory: true });
        }
      };
    })();

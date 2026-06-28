// Localization system for NeuroScan

let i18nData = {};
let currentLanguage = localStorage.getItem("neuroscan-language") || "en";

// Load translations
async function initI18n() {
  try {
    const response = await fetch("src/i18n.json");
    i18nData = await response.json();
    setLanguage(currentLanguage);
  } catch (error) {
    console.error("Failed to load translations:", error);
  }
}

// Get translated string
function t(key, defaultText = key) {
  const lang = currentLanguage;
  if (i18nData[lang] && i18nData[lang][key]) {
    return i18nData[lang][key];
  }
  if (i18nData["en"] && i18nData["en"][key]) {
    return i18nData["en"][key];
  }
  return defaultText;
}

// Set language
function setLanguage(lang) {
  if (lang === "en" || lang === "uk") {
    currentLanguage = lang;
    localStorage.setItem("neuroscan-language", lang);
    document.documentElement.lang = lang;
    updateLanguageButtons();
    updatePageLanguage();
  }
}

// Update language button states
function updateLanguageButtons() {
  const langEnBtn = document.querySelector("#lang-en");
  const langUkBtn = document.querySelector("#lang-uk");
  
  if (langEnBtn) {
    if (currentLanguage === "en") {
      langEnBtn.classList.add("active");
      langEnBtn.style.background = "var(--teal)";
      langEnBtn.style.color = "#ffffff";
    } else {
      langEnBtn.classList.remove("active");
      langEnBtn.style.background = "";
      langEnBtn.style.color = "";
    }
  }
  
  if (langUkBtn) {
    if (currentLanguage === "uk") {
      langUkBtn.classList.add("active");
      langUkBtn.style.background = "var(--teal)";
      langUkBtn.style.color = "#ffffff";
    } else {
      langUkBtn.classList.remove("active");
      langUkBtn.style.background = "";
      langUkBtn.style.color = "";
    }
  }
}

// Update all page text
function updatePageLanguage() {
  // Update navigation
  const navLinks = document.querySelectorAll(".nav a");
  if (navLinks.length > 0) {
    navLinks[0].textContent = t("diagnostics");
    if (navLinks[1]) navLinks[1].textContent = t("results");
    if (navLinks[2]) navLinks[2].textContent = t("history");
  }

  // Update buttons
  const loginBtn = document.querySelector("#loginBtn");
  const registerBtn = document.querySelector("#registerBtn");
  const logoutBtn = document.querySelector("#logoutBtn");
  const analyzeButton = document.querySelector("#analyzeButton");
  const reportButton = document.querySelector("#reportButton");
  const exportHistoryButton = document.querySelector("#exportHistoryButton");
  const importHistoryButton = document.querySelector("#importHistoryButton");
  const clearHistoryButton = document.querySelector("#clearHistoryButton");

  if (loginBtn) loginBtn.textContent = t("login");
  if (registerBtn) registerBtn.textContent = t("register");
  if (logoutBtn) logoutBtn.textContent = t("logout");
  if (analyzeButton) analyzeButton.textContent = t("analysis");
  if (reportButton) reportButton.textContent = t("report");
  if (exportHistoryButton) exportHistoryButton.textContent = t("export_history");
  if (importHistoryButton) importHistoryButton.textContent = t("import_history");
  if (clearHistoryButton) clearHistoryButton.textContent = t("clear_history");

  // Update labels
  const userDisplayName = document.querySelector("#userDisplayName");
  if (userDisplayName && userDisplayName.textContent === "User") {
    userDisplayName.textContent = t("user");
  }

  // Update model panel
  const modelLabel = document.querySelector(".side-panel .panel-label");
  const modelDescription = document.querySelector(".side-panel p");
  if (modelLabel) modelLabel.textContent = t("model");
  if (modelDescription) modelDescription.textContent = t("educational_prototype");

  // Update canvas placeholder text
  const scanCanvas = document.querySelector("#scanCanvas");
  if (scanCanvas) {
    redrawCanvasPlaceholder();
  }

  // Update language indicator
  const languageIndicator = document.querySelector("[data-current-language]");
  if (languageIndicator) {
    languageIndicator.textContent = currentLanguage === "en" ? "EN" : "UK";
  }
}

// Redraw canvas with localized text
function redrawCanvasPlaceholder() {
  const scanCanvas = document.querySelector("#scanCanvas");
  if (!scanCanvas) return;
  
  const scanCtx = scanCanvas.getContext("2d");
  
  scanCtx.clearRect(0, 0, scanCanvas.width, scanCanvas.height);
  scanCtx.fillStyle = "#e8e8e8";
  scanCtx.fillRect(0, 0, scanCanvas.width, scanCanvas.height);
  scanCtx.fillStyle = "#999";
  scanCtx.font = "18px sans-serif";
  scanCtx.textAlign = "center";
  scanCtx.fillText(t("upload_file_for_analysis"), 260, 278);
}

// Get current language
function getLanguage() {
  return currentLanguage;
}

// Toggle language
function toggleLanguage() {
  setLanguage(currentLanguage === "en" ? "uk" : "en");
}

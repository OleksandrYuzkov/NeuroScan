// Localization system for NeuroScan.

let i18nData = {};
let currentLanguage = localStorage.getItem("neuroscan-language") || "uk";

async function initI18n() {
  try {
    const response = await fetch("src/i18n.json");
    i18nData = await response.json();
  } catch (error) {
    console.error("Failed to load translations:", error);
  }
  setLanguage(currentLanguage, { persist: false });
}

function t(key, defaultText = key) {
  const langPack = i18nData[currentLanguage] || {};
  const fallbackPack = i18nData.en || {};
  return langPack[key] || fallbackPack[key] || defaultText;
}

function formatI18n(templateKey, values = {}) {
  return t(templateKey).replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

function setLanguage(lang, options = {}) {
  if (!["en", "uk"].includes(lang)) return;
  currentLanguage = lang;
  if (options.persist !== false) {
    localStorage.setItem("neuroscan-language", lang);
  }
  document.documentElement.lang = lang;
  updateLanguageButtons();
  updatePageLanguage();
  window.dispatchEvent(new CustomEvent("languagechange", { detail: { language: lang } }));
}

function updateLanguageButtons() {
  document.querySelectorAll("[data-language]").forEach((button) => {
    const active = button.dataset.language === currentLanguage;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  ["en", "uk"].forEach((lang) => {
    const button = document.querySelector(`#lang-${lang}`);
    if (!button) return;
    const active = lang === currentLanguage;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function updatePageLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n, element.textContent);
  });

  document.querySelectorAll("[data-i18n-html]").forEach((element) => {
    element.innerHTML = t(element.dataset.i18nHtml, element.innerHTML);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });

  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.setAttribute("title", t(element.dataset.i18nTitle));
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });

  const titleKey = document.body?.dataset.pageTitle;
  if (titleKey) {
    document.title = t(titleKey);
  }

  const descriptionKey = document.body?.dataset.pageDescription;
  const description = document.querySelector('meta[name="description"]');
  if (descriptionKey && description) {
    description.setAttribute("content", t(descriptionKey));
  }
}

function getLanguage() {
  return currentLanguage;
}

function getLocale() {
  return currentLanguage === "uk" ? "uk-UA" : "en-US";
}

function toggleLanguage() {
  setLanguage(currentLanguage === "en" ? "uk" : "en");
}

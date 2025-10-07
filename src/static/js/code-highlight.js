// Code syntax highlighting for LPS2
(function() {
  // Load highlight.js for syntax highlighting
  function loadHighlightJS() {
    if (window.hljs) return Promise.resolve();
    
    return new Promise((resolve) => {
      // Add the stylesheet
      const styleLink = document.createElement('link');
      styleLink.rel = 'stylesheet';
      styleLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css';
      document.head.appendChild(styleLink);
      
      // Add the script
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js';
      script.onload = () => {
        // Load common programming languages
        Promise.all([
          loadLanguage('javascript'),
          loadLanguage('python'),
          loadLanguage('java'),
          loadLanguage('bash'),
          loadLanguage('html'),
          loadLanguage('css')
        ]).then(resolve);
      };
      document.head.appendChild(script);
    });
  }
  
  function loadLanguage(lang) {
    return new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = `https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/${lang}.min.js`;
      script.onload = resolve;
      document.head.appendChild(script);
    });
  }
  
  // Apply syntax highlighting to all code blocks in the response
  function applyCodeHighlighting(element) {
    if (!window.hljs) return;
    
    const codeBlocks = element.querySelectorAll('pre code');
    codeBlocks.forEach(block => {
      if (!block.classList.contains('hljs')) {
        hljs.highlightElement(block);
        
        // Add language label if available
        const language = block.className.match(/language-(\w+)/);
        if (language && language[1]) {
          const label = document.createElement('div');
          label.className = 'code-language-label';
          label.textContent = language[1];
          block.parentElement.insertBefore(label, block);
        }
      }
    });
  }

  // Add copy button to each code block
  function addCodeBlockCopyButtons(element) {
    const codeBlocks = element.querySelectorAll('pre code');
    codeBlocks.forEach(block => {
      if (!block.parentElement.querySelector('.code-copy-btn')) {
        const copyButton = document.createElement('button');
        copyButton.className = 'code-copy-btn';
        copyButton.textContent = 'Copy';
        copyButton.addEventListener('click', () => {
          const code = block.textContent;
          navigator.clipboard.writeText(code).then(() => {
            copyButton.textContent = 'Copied!';
            setTimeout(() => {
              copyButton.textContent = 'Copy';
            }, 2000);
          });
        });
        block.parentElement.appendChild(copyButton);
      }
    });
  }
  
  // Add expand/collapse functionality to long code blocks
  function addCodeBlockExpanders(element) {
    const codeBlocks = element.querySelectorAll('pre code');
    const MAX_VISIBLE_LINES = 20;
    
    codeBlocks.forEach(block => {
      const lines = block.textContent.split('\n');
      if (lines.length > MAX_VISIBLE_LINES + 5) { // Only for significantly long blocks
        const wrapper = block.parentElement;
        
        if (!wrapper.classList.contains('expandable-code')) {
          wrapper.classList.add('expandable-code', 'collapsed');
          wrapper.style.maxHeight = (MAX_VISIBLE_LINES * 1.5) + 'em';
          wrapper.style.overflow = 'hidden';
          wrapper.style.position = 'relative';
          
          const expandBtn = document.createElement('button');
          expandBtn.className = 'code-expand-btn';
          expandBtn.textContent = 'Show more';
          expandBtn.addEventListener('click', () => {
            if (wrapper.classList.contains('collapsed')) {
              wrapper.classList.remove('collapsed');
              wrapper.style.maxHeight = 'none';
              expandBtn.textContent = 'Show less';
            } else {
              wrapper.classList.add('collapsed');
              wrapper.style.maxHeight = (MAX_VISIBLE_LINES * 1.5) + 'em';
              expandBtn.textContent = 'Show more';
            }
          });
          
          const lineCount = document.createElement('div');
          lineCount.className = 'code-line-count';
          lineCount.textContent = `${lines.length} lines`;
          
          const expandControls = document.createElement('div');
          expandControls.className = 'code-expand-controls';
          expandControls.appendChild(lineCount);
          expandControls.appendChild(expandBtn);
          
          wrapper.appendChild(expandControls);
        }
      }
    });
  }

  // Initialize all code enhancement features
  window.LPS2CodeHighlight = {
    init: function() {
      loadHighlightJS().then(() => {
        // Find any existing code in the page
        const chatBox = document.getElementById('chatBox');
        if (chatBox) {
          applyCodeHighlighting(chatBox);
          addCodeBlockCopyButtons(chatBox);
          addCodeBlockExpanders(chatBox);
        }
      });
    },
    
    // Process a newly added response element
    processElement: function(element) {
      if (window.hljs) {
        applyCodeHighlighting(element);
        addCodeBlockCopyButtons(element);
        addCodeBlockExpanders(element);
      } else {
        loadHighlightJS().then(() => {
          applyCodeHighlighting(element);
          addCodeBlockCopyButtons(element);
          addCodeBlockExpanders(element);
        });
      }
    }
  };
})();

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', function() {
  window.LPS2CodeHighlight.init();
});
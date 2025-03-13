import asyncio
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.dom.service import DomService
from browser_use.dom.views import DOMElementNode, DOMState, DOMTextNode, SelectorMap


@pytest.fixture
async def browser():
    """Fixture to create a Browser instance."""
    browser = Browser(
        config=BrowserConfig(
            headless=True,
        )
    )
    yield browser
    await browser.close()


@pytest.fixture
async def browser_context(browser):
    """Fixture to create a BrowserContext instance."""
    config = BrowserContextConfig(
        disable_security=True,
        wait_for_network_idle_page_load_time=2,
    )
    context = BrowserContext(browser=browser, config=config)
    async with context as ctx:
        yield ctx


@pytest.fixture
async def dom_service(browser_context):
    """Fixture to create a DomService instance."""
    page = await browser_context.get_current_page()
    dom_service = DomService(page)
    return dom_service


@pytest.fixture
async def mock_page():
    """Fixture for creating a mock page for testing."""
    mock = MagicMock()
    mock.evaluate.return_value = 2  # For the basic JS eval test
    return mock


@pytest.fixture
def mock_dom_service(mock_page):
    """Fixture for creating a DomService with a mock page."""
    service = DomService(mock_page)
    
    # Mock the JS code to avoid reading from resources
    service.js_code = "function mockJsCode() { return true; }"
    
    return service


class TestDomExtraction:
    """Test suite for DOM extraction functionality."""

    @pytest.mark.asyncio
    async def test_basic_page_setup(self, browser_context):
        """Test that we can set up a page and navigate to a test URL."""
        page = await browser_context.get_current_page()
        assert page is not None
        
        # Navigate to a simple test page
        await page.goto("about:blank")
        title = await page.title()
        assert title == ""  # about:blank has an empty title
    
    @pytest.mark.asyncio
    async def test_get_clickable_elements_basic(self, mock_dom_service):
        """Test the basic functionality of get_clickable_elements."""
        # Mock the _build_dom_tree method
        mock_dom_service._build_dom_tree = MagicMock()
        
        # Create a simple DOM tree and selector map
        element = DOMElementNode(
            tag_name="div",
            xpath="//div",
            attributes={"id": "test-div"},
            children=[],
            is_visible=True,
            is_interactive=True,
            highlight_index=1
        )
        
        selector_map = {1: element}
        mock_dom_service._build_dom_tree.return_value = (element, selector_map)
        
        # Call the method
        result = await mock_dom_service.get_clickable_elements()
        
        # Verify the result
        assert isinstance(result, DOMState)
        assert result.element_tree == element
        assert result.selector_map == selector_map
        assert len(result.selector_map) == 1
        assert 1 in result.selector_map
        
        # Verify the method was called with the correct parameters
        mock_dom_service._build_dom_tree.assert_called_once_with(
            True, -1, 0
        )
    
    @pytest.mark.asyncio
    async def test_different_viewport_expansions(self, mock_dom_service):
        """Test DOM extraction with different viewport expansions."""
        # Create a test implementation that can track calls with different expansions
        viewport_calls = []
        
        async def mock_build_dom_tree(highlight, focus, expansion):
            viewport_calls.append(expansion)
            element = DOMElementNode(
                tag_name="div",
                xpath="//div",
                attributes={},
                children=[],
                is_visible=True,
                highlight_index=1
            )
            return element, {1: element}
        
        mock_dom_service._build_dom_tree = mock_build_dom_tree
        
        # Test with different viewport expansions
        expansions = [0, 100, 500, -1]
        for expansion in expansions:
            await mock_dom_service.get_clickable_elements(viewport_expansion=expansion)
        
        # Verify all expansions were used
        assert viewport_calls == expansions
    
    @pytest.mark.asyncio
    async def test_highlighting_functionality(self, mock_dom_service):
        """Test the element highlighting functionality."""
        highlight_calls = []
        
        async def mock_build_dom_tree(highlight, focus, expansion):
            highlight_calls.append((highlight, focus))
            element = DOMElementNode(
                tag_name="div",
                xpath="//div",
                attributes={},
                children=[],
                is_visible=True,
                highlight_index=1 if highlight else None
            )
            return element, {1: element} if highlight else {}
        
        mock_dom_service._build_dom_tree = mock_build_dom_tree
        
        # Test with highlighting on and off, and with different focus elements
        test_cases = [
            (True, -1),   # Highlight all elements
            (False, -1),  # No highlighting
            (True, 1)     # Highlight specific element
        ]
        
        for highlight, focus in test_cases:
            result = await mock_dom_service.get_clickable_elements(
                highlight_elements=highlight,
                focus_element=focus
            )
            
            # Verify selector map has elements only when highlighting
            if highlight:
                assert len(result.selector_map) == 1
            else:
                assert len(result.selector_map) == 0
        
        # Verify all highlight configurations were used
        assert highlight_calls == test_cases
    
    @pytest.mark.asyncio
    async def test_error_handling_js_evaluation(self, mock_dom_service):
        """Test error handling during JavaScript evaluation."""
        # Make the page.evaluate method raise an exception
        mock_dom_service.page.evaluate.side_effect = Exception("JavaScript evaluation failed")
        
        # Verify that the exception is propagated
        with pytest.raises(Exception, match="JavaScript evaluation failed"):
            await mock_dom_service.get_clickable_elements()
    
    @pytest.mark.asyncio
    async def test_error_handling_dom_construction(self, mock_dom_service):
        """Test error handling during DOM tree construction."""
        # Make the page.evaluate return valid data
        mock_dom_service.page.evaluate.return_value = {
            "map": {},  # Empty node map to cause an error in _construct_dom_tree
            "rootId": "non_existent_id"
        }
        
        # Override _construct_dom_tree to simulate the actual implementation
        async def mock_construct_dom_tree(eval_page):
            js_node_map = eval_page['map']
            js_root_id = eval_page['rootId']
            
            # This will fail because the rootId doesn't exist in the map
            return None, {}
        
        mock_dom_service._construct_dom_tree = mock_construct_dom_tree
        
        # Verify that the exception is raised
        with pytest.raises(ValueError, match="Failed to parse HTML to dictionary"):
            await mock_dom_service._build_dom_tree(True, -1, 0)
    
    @pytest.mark.asyncio
    @patch('browser_use.dom.service.logger')
    async def test_debug_mode_logging(self, mock_logger, mock_dom_service):
        """Test logging in debug mode."""
        # Set up the logger to return DEBUG level
        mock_logger.getEffectiveLevel.return_value = logging.DEBUG
        
        # Mock the page.evaluate to return performance metrics
        mock_dom_service.page.evaluate.return_value = {
            "map": {},
            "rootId": "test_id",
            "perfMetrics": {"parseTime": 10, "processTime": 20}
        }
        
        # Create a simplified _construct_dom_tree implementation
        async def mock_construct_dom_tree(eval_page):
            element = DOMElementNode(
                tag_name="html",
                xpath="//html",
                attributes={},
                children=[],
                is_visible=True
            )
            return element, {}
        
        mock_dom_service._construct_dom_tree = mock_construct_dom_tree
        
        # Call the method
        await mock_dom_service._build_dom_tree(True, -1, 0)
        
        # Verify debug logs were called
        mock_logger.debug.assert_called()


@pytest.mark.integration
class TestDomExtractionIntegration:
    """Integration tests for DOM extraction with real browser."""
    
    TEST_URLS = [
        "https://example.com",
        "about:blank"
    ]
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("url", TEST_URLS)
    async def test_real_page_extraction(self, dom_service, browser_context, url):
        """Test extracting DOM elements from a real page."""
        page = await browser_context.get_current_page()
        await page.goto(url)
        
        # Extract DOM with different viewport expansions
        for expansion in [0, 100, -1]:
            dom_state = await dom_service.get_clickable_elements(
                highlight_elements=True,
                viewport_expansion=expansion
            )
            
            # Basic assertions to verify we got some data
            assert dom_state is not None
            assert dom_state.element_tree is not None
            assert isinstance(dom_state.selector_map, dict)
            
            # Verify element structure
            assert dom_state.element_tree.tag_name.lower() == "html"
            
            # Try to find the body element in children
            body_found = False
            for child in dom_state.element_tree.children:
                if isinstance(child, DOMElementNode) and child.tag_name.lower() == "body":
                    body_found = True
                    break
            
            assert body_found, f"Body element not found for URL {url} with expansion {expansion}"


if __name__ == "__main__":
    asyncio.run(pytest.main(["-v"]))


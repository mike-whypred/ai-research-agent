import streamlit as st
from openai import OpenAI
import time
import re
from datetime import datetime
import yaml
from markdown import markdown

# Page configuration
st.set_page_config(
    page_title="Sales Prospect Research Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "AI-powered sales prospect research tool for generating comprehensive company reports"
    }
)

# Hide the GitHub icon and other default elements
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.css-1d391kg, .css-1lcbmhc, .css-1cypcdb, .css-17eq0hr {
    min-width: 400px !important;
    max-width: 400px !important;
}
section[data-testid="stSidebar"] > div {
    min-width: 400px !important;
    max-width: 400px !important;
}
section[data-testid="stSidebar"]:not([aria-expanded="false"]) {
    min-width: 400px !important;
    max-width: 400px !important;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Main app content starts here
st.title("Generate Report")
st.caption("Report will populate below")

# Initialize Perplexity client
client = OpenAI(api_key=st.secrets["PERPLEXITY_API_KEY"], base_url="https://api.perplexity.ai")

# Load questions and system prompt from YAML config
def load_config():
    try:
        with open('report-config.yaml', 'r') as file:
            config = yaml.safe_load(file)
            return config['questions'], config.get('system_prompt', '')
    except Exception as e:
        st.error(f"Error loading config: {str(e)}")
        return [], ''

# Initialize session state for custom questions and question toggles if not already present
if 'custom_questions' not in st.session_state:
    st.session_state.custom_questions = {}
if 'question_toggles' not in st.session_state:
    st.session_state.question_toggles = {}

# Load template questions and system prompt
template_questions, system_prompt = load_config()

def get_perplexity_response(query, context="", question_id=None):
    try:
        response = client.chat.completions.create(
            model=st.secrets["PPLX_MODEL"],
            messages=[
                {"role": "system", "content": f"""{system_prompt}
                                                Previous context: {context}""" if context else system_prompt},
                {"role": "user", "content": query}
            ]
        )
        # Clean up the response text
        response_text = response.choices[0].message.content
        response_text = response_text.replace('$', '')
        
        # Convert any remaining headers to level 5
        response_text = re.sub(r'^#+ (.+)$', r'##### \1', response_text, flags=re.MULTILINE)
        
        # Extract citations from the response object
        citations = response.citations if hasattr(response, 'citations') else []
        
        # Handle stacked references with a more comprehensive regex
        if citations:
            # First replace stacked references like [1][4] with a temporary format
            response_text = re.sub(r'\[(\d+)\]\[(\d+)\]', r'[REF_\1_\2]', response_text)
            
            # Then replace single references
            for i, _ in enumerate(citations, 1):
                response_text = re.sub(f'\\[{i}\\](?!\\[)', f'[{question_id}-{i}]', response_text)
            
            # Finally, replace the temporary stacked references
            response_text = re.sub(r'\[REF_(\d+)_(\d+)\]', 
                                 lambda m: f'[{question_id}-{m.group(1)}][{question_id}-{m.group(2)}]', 
                                 response_text)
        
        return response_text, citations
    except Exception as e:
        print(f"Error in get_perplexity_response: {str(e)}")  # Debug print
        print(f"Response object: {response}")  # Debug print
        return f"Error: {str(e)}", []

# Initialize session state for analysis results if not already present
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'company_analyzed' not in st.session_state:
    st.session_state.company_analyzed = None

# Sidebar
with st.sidebar:
    st.header("Business Development Research Agent")
    st.markdown("""
        Enter the name of a company to research as a potential sales prospect. The default questions and number of questions can be customised.

        • The information comes from reputable online sources, which are cited at the end of the report
        
        • A coherent report is synthesized using an LLM and is downloadable as an HTML file
        
        • Customised questions can be saved as templates and reused
    """)

    st.divider()

    company_name = st.text_input("Enter Company Name")

    _ , _,  col3 = st.columns([2,2,1])
    
    with col3:
        run_analysis = st.button("Run")

    st.divider()

    # Add export/import section
    st.write("Import Question Template")
    
    # Initialize session state for imported data if not present
    if 'imported_data' not in st.session_state:
        st.session_state.imported_data = None
    
    # Import functionality
    uploaded_file = st.file_uploader("Import Questions", type='yaml', label_visibility="collapsed", key="question_uploader")
    if uploaded_file is not None and uploaded_file != st.session_state.imported_data:
        try:
            # Read and parse YAML
            imported_config = yaml.safe_load(uploaded_file)
            st.session_state.imported_data = uploaded_file
            
            # Validate structure
            if not isinstance(imported_config, dict) or 'questions' not in imported_config:
                st.error("Invalid YAML structure. File must contain a 'questions' list.")
            else:
                # Create a mapping of imported questions
                imported_questions = {
                    q['id']: q['text'] 
                    for q in imported_config['questions'] 
                    if 'id' in q and 'text' in q
                }
                
                # Update session state for all template questions
                for question in template_questions:
                    q_id = question['id']
                    if q_id in imported_questions:
                        st.session_state[f"custom_q_{q_id}"] = imported_questions[q_id]
                        st.session_state[f"toggle_{q_id}"] = True
                    else:
                        st.session_state[f"custom_q_{q_id}"] = question['text']
                        st.session_state[f"toggle_{q_id}"] = False
                
                num_imported = len(imported_questions)
                st.success(f"Imported {num_imported} questions successfully!")
                st.rerun()

        except Exception as e:
            st.error(f"Error importing questions: {str(e)}")

    st.divider()

    st.write("Customize Questions:")
    for question in template_questions:
        question_id = question['id']
        default_text = question['text']
        
        # Initialize session state for this question if not present
        if f"custom_q_{question_id}" not in st.session_state:
            st.session_state[f"custom_q_{question_id}"] = default_text
        if f"toggle_{question_id}" not in st.session_state:
            st.session_state[f"toggle_{question_id}"] = True
        
        # Create a toggle for this question without default value
        toggle_value = st.toggle(
            f"Question {question_id}",
            key=f"toggle_{question_id}"
        )
        
        # Update the question_toggles dictionary
        st.session_state.question_toggles[question_id] = toggle_value
        
        # Create an input box for this question if it's enabled
        if toggle_value:
            custom_text = st.text_input(
                f"Question {question_id}",
                key=f"custom_q_{question_id}",
                label_visibility="collapsed"
            )
            # Update only the custom_questions dictionary
            st.session_state.custom_questions[question_id] = custom_text.strip()
    
    # Create two columns for the buttons
    col1, col2 = st.columns(2)
    
    with col1:
        sidebar_run = st.button("Run", key="sidebar_run")
    
    with col2:
        yaml_str = yaml.dump({
            'questions': [
                {   
                    'id': q['id'],
                    'text': st.session_state.custom_questions[q['id']]
                }
                for q in template_questions
                if st.session_state.question_toggles[q['id']]
            ]
        }, sort_keys=False)
        st.download_button(
            label="Export as Template",
            data=yaml_str,
            file_name="custom_questions.yaml", 
            mime="text/yaml",
            use_container_width=True  # Make button fill column width
        )

# Main content
if (run_analysis or sidebar_run) and company_name:
    # Check P_FLAG before proceeding
    if st.secrets.get("P_FLAG") == "Y":
        error_message = {'error': {'message': 'insufficient quota, please refer to platform documentations', 'type': '403'}}
        st.error(str(error_message))
        st.stop()
    
    context = ""
    html_content = ""
    results = []  # Store all results
    all_citations = []  # Store all citations with their question IDs
    
    # Update the filtering of active questions to consider toggles
    active_questions = [
        question for question in template_questions 
        if st.session_state.custom_questions[question['id']].strip() and 
        st.session_state.question_toggles[question['id']]
    ]
    
    # Process each non-blank question
    for i, question in enumerate(active_questions, 1):
        question_id = question['id']
        question_text = st.session_state.custom_questions[question_id]
        
        st.header(f"{i}. {question_text}")
        
        with st.spinner(f'generating response for question {i} of {len(active_questions)}...'):
            formatted_question = f"Regarding {company_name}: {question_text}. Please provide detailed information based on the latest available data."
            response, citations = get_perplexity_response(formatted_question, context, question_id)
            
            # Store citations with question ID
            if citations:
                all_citations.append({
                    'question_id': question_id,
                    'question_num': i,
                    'citations': citations
                })
            
            # Store result
            results.append({
                'question': f"{i}. {question_text}",
                'response': response
            })
            
            # Display the response
            st.markdown(response)
            st.divider()
            
            # Update context and HTML content
            context += f"\nQ: {question_text}\nA: {response}\n"
            
            # Convert markdown to HTML before adding to html_content
            html_response = markdown(response)
            html_content += f"""
            <div class="question">{i}. {question_text}</div>
            <div class="answer">{html_response}</div>
            <hr>
            """
            
            time.sleep(1)

    # Display all citations at the end if there are any
    references_html = ""
    if all_citations:
        st.header("References")
        references_html = "<h2>References</h2>"
        for citation_group in all_citations:
            q_id = citation_group['question_id']
            for i, citation in enumerate(citation_group['citations'], 1):
                # Extract URL if present in the citation
                url_match = re.search(r'https?://[^\s<>"]+|www\.[^\s<>"]+', citation)
                if url_match:
                    url = url_match.group()
                    # Display as regular text in Streamlit
                    st.markdown(f"[{q_id}-{i}] {citation}")
                    # Create hyperlink in HTML
                    references_html += f'<p>[{q_id}-{i}] <a href="{url}" target="_blank">{citation}</a></p>'
                else:
                    # If no URL found, display as regular text
                    st.markdown(f"[{q_id}-{i}] {citation}")
                    references_html += f"<p>[{q_id}-{i}] {citation}</p>"

    # Store results in session state
    st.session_state.analysis_results = {
        'results': results,
        'html_content': html_content,
        'context': context,
        'references_html': references_html
    }
    st.session_state.company_analyzed = company_name
    
    # Add download button after analysis is complete
    html_full_content = f"""
    <html>
    <head>
        <title>{company_name} - Sales Prospect Research Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .question {{ font-size: 1.2em; font-weight: bold; margin-top: 20px; }}
            .answer {{ margin-bottom: 20px; }}
            hr {{ margin: 20px 0; }}
            .answer p {{ margin: 10px 0; }}
            .answer ul, .answer ol {{ margin: 10px 0; padding-left: 20px; }}
            strong {{ color: #1a1a1a; }}
        </style>
    </head>
    <body>
        <h1>{company_name} - Sales Prospect Research Report</h1>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        {html_content}
        {references_html}
    </body>
    </html>
    """
    st.download_button(
        label="Download Report as HTML",
        data=html_full_content,
        file_name=f"{company_name}_sales_prospect_report.html",
        mime="text/html"
    )

# Display existing results if available
elif st.session_state.analysis_results is not None:
    for result in st.session_state.analysis_results['results']:
        st.header(result['question'])
        st.markdown(result['response'])
        st.divider()
    
    # Show download button for existing results
    html_full_content = f"""
    <html>
    <head>
        <title>{st.session_state.company_analyzed} - Sales Prospect Research Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .question {{ font-size: 1.2em; font-weight: bold; margin-top: 20px; }}
            .answer {{ margin-bottom: 20px; }}
            hr {{ margin: 20px 0; }}
            .answer p {{ margin: 10px 0; }}
            .answer ul, .answer ol {{ margin: 10px 0; padding-left: 20px; }}
            strong {{ color: #1a1a1a; }}
        </style>
    </head>
    <body>
        <h1>{st.session_state.company_analyzed} - Sales Prospect Research Report</h1>
        {st.session_state.analysis_results['html_content']}
        {st.session_state.analysis_results.get('references_html', '')}
    </body>
    </html>
    """
    st.download_button(
        label="Download Report as HTML",
        data=html_full_content,
        file_name=f"{st.session_state.company_analyzed}_sales_prospect_report.html",
        mime="text/html"
    ) 
import streamlit as st
import pandas as pd
import io
import uuid
import base64
import re
import openpyxl

st.set_page_config(page_title="PARALUX Metadata Processor", layout="wide")

# Custom CSS for styling (same as before)
st.markdown("""
<style>
    .main-title { font-size: 32px; font-weight: bold; text-align: center; margin-bottom: 30px; }
    .download-button { text-align: center; margin-top: 20px; }
    .stApp > header { display: none !important; }
    .block-container { max-width: 1000px; padding-top: 1rem; padding-bottom: 10rem; }
    .custom-button {
        background-color: #4CAF50;
        border: none;
        color: white;
        padding: 15px 32px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 4px;
        transition: all 0.3s ease 0s;
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
    }
    .custom-button:hover {
        background-color: #45a049;
        box-shadow: 0 15px 20px rgba(0, 0, 0, 0.2);
        transform: translateY(-7px);
    }
</style>
""", unsafe_allow_html=True)


def excel_column_to_number(column_letter):
    """Convert Excel column letter to column index"""
    return openpyxl.utils.column_index_from_string(column_letter) - 1


def process_composers(composers):
    composer_list = composers.split(',')
    names = []
    shares = []
    pros = []
    cae_ipis = []
    for composer in composer_list:
        match = re.match(r'(.*?)\s*\((.*?)\)\s*(\d+)%\s*\[(.*?)\]', composer.strip())
        if match:
            names.append(match.group(1))
            pros.append(match.group(2))
            shares.append(match.group(3) + '%')
            cae_ipis.append(match.group(4))
    return (' / '.join(f"{name} ({share})" for name, share in zip(names, shares)),
            ' / '.join(cae_ipis),
            ' / '.join(pros))


def process_publishers(publishers):
    publisher_list = publishers.split(',')
    names = []
    shares = []
    for publisher in publisher_list:
        match = re.match(r'(.*?)\s*\((.*?)\)\s*(\d+)%\s*\[(.*?)\]', publisher.strip())
        if match:
            names.append(match.group(1))
            shares.append(match.group(3) + '%')
    return ' / '.join(f"{name} ({share})" for name, share in zip(names, shares))


import re
import pandas as pd


def get_base_track_name(full_track_name):
    return full_track_name.split(' - ')[0] if ' - ' in full_track_name else full_track_name


def version_sort_key(version):
    version = str(version).lower()
    if version == 'full':
        return (0, '')
    elif version.startswith('no '):
        return (1, version)
    elif re.match(r'\d+\s*second', version):
        seconds = int(re.search(r'\d+', version).group())
        return (2, seconds)
    elif 'stem' in version:
        return (3, version)
    else:
        return (4, version)


def process_excel_files(uploaded_files, column_mapping):
    combined_data = []

    for file in uploaded_files:
        df = pd.read_excel(file, header=None)

        for _, row in df.iterrows():
            track_name = str(row[excel_column_to_number(column_mapping['track_name'])])
            version = str(row[excel_column_to_number(column_mapping['version'])])

            # Skip header rows or rows with incomplete data
            if ('tracktitle' in track_name.lower() or
                    track_name.strip() == '' or
                    'cdtitle' in str(row[excel_column_to_number(column_mapping['album'])]).lower()):
                continue

            full_track_name = f"{track_name} {version}" if version.lower() != 'full' else track_name

            composers, composer_cae_ipis, composer_pros = process_composers(
                row[excel_column_to_number(column_mapping['composers'])])
            publishers = process_publishers(row[excel_column_to_number(column_mapping['publishers'])])

            new_row = {
                'Track Name': full_track_name,
                'Version': 'Main' if version.lower() == 'full' else '',
                'Artist': 'Paralux',
                'Album': row[excel_column_to_number(column_mapping['album'])],
                'Composer': composers,
                'CAE/IPI': composer_cae_ipis,
                'Label': 'Paralux',
                'Publisher': publishers,
                'PRO': composer_pros
            }

            combined_data.append(new_row)

    combined_df = pd.DataFrame(combined_data)

    # Sort the DataFrame
    combined_df['Base Track Name'] = combined_df['Track Name'].apply(get_base_track_name)
    combined_df['Version Sort Key'] = combined_df['Track Name'].apply(
        lambda x: version_sort_key(x.split(' - ')[-1] if ' - ' in x else 'full'))

    combined_df = combined_df.sort_values(
        by=['Base Track Name', 'Version Sort Key']
    )

    # Remove temporary columns used for sorting
    combined_df = combined_df.drop(columns=['Base Track Name', 'Version Sort Key'])

    return combined_df


def get_binary_file_downloader_html(df, filename):
    towrite = io.BytesIO()
    df.to_excel(towrite, index=False, engine='openpyxl')
    towrite.seek(0)
    b64 = base64.b64encode(towrite.read()).decode()
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}"><button class="custom-button">Download Processed Excel File</button></a>'


# Main app layout
st.markdown("<h1 class='main-title'>PARALUX Metadata Processor</h1>", unsafe_allow_html=True)

# Create a centered column
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    uploaded_files = st.file_uploader("Upload Excel files", type="xlsx", accept_multiple_files=True)

    if uploaded_files:
        column_mapping = {
            'track_name': 'R',
            'version': 'S',
            'album': 'P',
            'composers': 'W',
            'publishers': 'AA'
        }

        # Add filename input with default value
        output_filename = st.text_input("Enter output filename", value="PLX Schedule A.xlsx")

        if st.button("Process and Combine Files"):
            with st.spinner("Processing files..."):
                combined_df = process_excel_files(uploaded_files, column_mapping)
                if not combined_df.empty:
                    st.success(f"Files processed and combined successfully! Total rows: {len(combined_df)}")
                    st.markdown("<div class='download-button'>", unsafe_allow_html=True)
                    st.markdown(get_binary_file_downloader_html(combined_df, output_filename), unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.error("No data was processed. Please check your input files and try again.")
    else:
        st.info("Please upload Excel (.xlsx) files to process and combine.")
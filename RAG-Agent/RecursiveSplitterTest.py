from sentence_transformers import SentenceTransformer
from langchain.text_splitter import SentenceTransformersTokenTextSplitter


from langchain.text_splitter import RecursiveCharacterTextSplitter

text = "This is a long document that needs to be split into smaller chunks for processing.thsi is second line.\n\nThis si a third line. \nThis is offcourse"
splitter = RecursiveCharacterTextSplitter(
    chunk_size=100,  # Max 20 characters per chunk
    #If a chunk is already smaller than chunk_size, it stops splitting further, even if additional separators are present within that chunk.
    chunk_overlap=20,  # 5 characters overlap between chunks
    #chunk overlap occurs only when splitting occurs.
    separators=["\n\n", "\n", " ", ""]
)
chunks = splitter.split_text(text)
print(chunks)

"""
Recursive Splitting Logic:
The splitter works recursively: it tries the separators in order (\n\n, \n, " ", "") and splits the text into chunks that are smaller than chunk_size.
If a chunk is already smaller than chunk_size, it stops splitting further, even if additional separators are present within that chunk.
Size of the Last Chunk:
The last chunk ('This si a third line. \nThis is offcourse') is 40 characters long, which is well below the chunk_size of 100 characters.
Since this chunk already satisfies the size constraint, the splitter does not attempt to split it further, even though it contains a \n.
Overlap Consideration:
The chunk_overlap=20 parameter ensures that 20 characters from the previous chunk are included in the next chunk, but this applies only when splitting occurs.
Since the last chunk is already small enough, no further splitting is triggered, and overlap doesn’t come into play here.
Separator Precedence:
The splitter processes separators in order: \n\n, \n, " ", "".
The text is first split at \n\n, producing two parts:
"This is a long document that needs to be split into smaller chunks for processing.thsi is second line."
"This si a third line. \nThis is offcourse".
The first part (110 characters) exceeds chunk_size=100, so it’s split further at a space (" "), resulting in:
'This is a long document that needs to be split into smaller chunks for processing.thsi is second' (95 characters).
'is second line.' (15 characters).
The second part (40 characters) is already under chunk_size=100, so no further splitting occurs, even though it contains a \n.
Implementation Detail:
The RecursiveCharacterTextSplitter does not split chunks that are already within the chunk_size limit, even if they contain separators. 
This is a design choice to avoid unnecessary fragmentation when the chunk is already small enough for downstream processing.

"""
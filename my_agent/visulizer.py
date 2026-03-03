from langchain_core.runnables.graph import MermaidDrawMethod
from IPython.display import Image, display
# Assuming build_graph is imported from your local utils
from utils.graphv3 import build_graph 

app = build_graph(return_builder=False) # Ensure this is the compiled graph

# Generate the graph image
graph_image = app.get_graph().draw_mermaid_png(
    draw_method=MermaidDrawMethod.API,
)

# Display or Save
display(Image(graph_image))

# Optional: Since you are running this from PowerShell and not a Jupyter Notebook, 
# display() won't show anything. Save it to a file instead:
with open("graphv3.png", "wb") as f:
    f.write(graph_image)
print("Graph saved as graphv3.png")
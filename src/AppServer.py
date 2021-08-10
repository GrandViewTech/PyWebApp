from flask import Flask, render_template
from jinja2 import Environment, FileSystemLoader
#from weasyprint import HTML
import os
import pdfkit
sep=os.path.sep

env = Environment(loader=FileSystemLoader('templates'))

app = Flask(__name__, template_folder='templates')





def render_bill():
    template = env.get_template("Bill.html")
    template_vars = {"title": "Sales Funnel Report - National"}
    html_out = template.render(template_vars)
    file_name='output'+sep+'report1'
    html_file=file_name+".html"
    pdf_file=file_name+".pdf"
    file=open(html_file,'w+')
    file.write(html_out)
    print(html_out)
    pdfkit.from_string(html_out,pdf_file)
    print("Report Generated")


## REST ##

@app.route("/")
def template_test():
    page='Home.html'
    template = env.get_template(page)
    vars={'my_list':[1,2,3],'title':'dfdfdfd'}
    return template.render(vars)



def main():
    # starting Server
    render_bill()
    #app.run(debug=True)
    #print("\nStarting Society Management Application")



if __name__ == '__main__': main()
from fastapi import FastAPI
app = FastAPI(title='Reflection Agent')
@app.get('/')
def root(): return {'status': 'Reflection Agent Online'}

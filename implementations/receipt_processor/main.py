from fastapi import FastAPI
app = FastAPI(title='Receipt Worker')
@app.get('/')
def root(): return {'status': 'Worker Online'}
